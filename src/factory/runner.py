from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import structlog
from substrate import Substrate
from substrate._types import ActorMetadata

from factory.channel import Channel
from factory.config import FactoryConfig
from factory.context import derive_context
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    work_root,
    write_artifact,
)

log = structlog.get_logger()


def run_worker(config: FactoryConfig, channel: Channel) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        worker_loop(sub, config, channel)
    finally:
        sub.close()


def worker_loop(sub: Substrate, config: FactoryConfig, channel: Channel) -> None:
    actor_id = f"factory-worker-{channel.name}"
    for role_name in config.worker_roles:
        sub.register_actor_role(actor_id, role_name)
    poll_interval = config.poll_interval_seconds
    while True:
        claimed = False
        for role_name in config.worker_roles:
            page = sub.query_work_items(
                workflow_name=config.workflow_name,
                workflow_version=config.workflow_version,
                current_states=["new"],
                claimable_now=True,
                page_size=10,
            )
            for wi in page.items:
                if wi.work_item_type != "interface_spec":
                    continue
                claim = sub.acquire_claim(
                    wi.work_item_id, actor_id, config.claim_ttl_seconds
                )
                log.info(
                    "claim_acquired",
                    work_item_id=str(wi.work_item_id),
                    attempt=claim.attempt_number,
                )
                try:
                    process_work_item(sub, config, channel, wi, actor_id, claim)
                    claimed = True
                except Exception:
                    log.exception("process_error", work_item_id=str(wi.work_item_id))
                    sub.release_claim(wi.work_item_id, actor_id)
                break
            if claimed:
                break
        if not claimed:
            time.sleep(poll_interval)


def process_work_item(
    sub: Substrate,
    config: FactoryConfig,
    channel: Channel,
    wi,
    actor_id: str,
    claim,
) -> None:
    work_item_id = str(wi.work_item_id)
    attempt_number = claim.attempt_number
    role_name = "interface_architect"
    wr = work_root(Path(config.workspace_root))
    resumable = find_resumable_artifact(wr, work_item_id)
    if resumable is not None:
        log.info(
            "resuming_from_artifact",
            work_item_id=work_item_id,
            attempt=resumable[0],
        )
        _resume_and_submit(
            sub, wi, resumable[0], resumable[1], actor_id, channel
        )
        return

    ctx = derive_context(sub, wi.work_item_id, role_name)
    role_config = config.get_role_config(role_name)
    timeout = role_config.timeout_seconds if role_config else config.claim_ttl_seconds
    ad = attempt_dir(wr, work_item_id, attempt_number)
    inputs_dir = wr / work_item_id / "inputs"
    invoke_result = channel.invoke(role_name, ctx.context_hash, inputs_dir, ad, timeout)

    if not invoke_result.success:
        _handle_invoke_failure(
            sub, wi, ad, invoke_result, actor_id, channel,
            role_name, attempt_number, ctx,
        )
        return

    artifact_path = ad / invoke_result.artifact_name
    artifact_data = artifact_path.read_bytes()
    sha = compute_sha256(artifact_data)
    manifest = ArtifactManifest(
        attempt_number=attempt_number,
        work_item_id=work_item_id,
        artifact_name=invoke_result.artifact_name,
        artifact_sha256=sha,
        artifact_size=len(artifact_data),
        actor_id=actor_id,
        channel=channel.name,
        family=channel.family,
        model=None,
        context_hash=ctx.context_hash,
    )
    write_artifact(ad, invoke_result.artifact_name, artifact_data, manifest)
    actor_metadata = ActorMetadata(
        role=role_name,
        channel=channel.name,
        family=channel.family,
        attempt_n=attempt_number,
        context_hash=ctx.context_hash,
    ).to_dict()
    sub.transition(
        wi.work_item_id,
        "submit",
        actor_id,
        actor_metadata=actor_metadata,
        custom_fields={
            "artifact_path": str(artifact_path),
            "artifact_hash": sha,
        },
    )


def _handle_invoke_failure(
    sub: Substrate,
    wi,
    ad: Path,
    invoke_result,
    actor_id: str,
    channel: Channel,
    role_name: str,
    attempt_number: int,
    ctx,
) -> None:
    work_item_id = wi.work_item_id
    if invoke_result.error_message == "cannot_proceed":
        cp_path = ad / "cannot_proceed.json"
        if cp_path.exists():
            cp_data = cp_path.read_bytes()
            sub.transition(
                work_item_id,
                "submit",
                actor_id,
                actor_metadata=ActorMetadata(
                    role=role_name,
                    channel=channel.name,
                    family=channel.family,
                    attempt_n=attempt_number,
                    context_hash=ctx.context_hash,
                ).to_dict(),
                custom_fields={
                    "diagnostics": json.loads(cp_data),
                },
            )
        else:
            sub.release_claim(work_item_id, actor_id)
        return
    log.error(
        "channel_invoke_failed",
        work_item_id=str(work_item_id),
        error=invoke_result.error_message,
    )
    sub.release_claim(work_item_id, actor_id)


def _resume_and_submit(
    sub: Substrate,
    wi,
    resumable_attempt: int,
    manifest: ArtifactManifest,
    actor_id: str,
    channel: Channel,
) -> None:
    actor_metadata = {
        "role": "interface_architect",
        "channel": manifest.channel or channel.name,
        "family": manifest.family or channel.family,
        "attempt_n": resumable_attempt,
        "context_hash": manifest.context_hash,
    }
    sub.transition(
        wi.work_item_id,
        "submit",
        actor_id,
        actor_metadata=actor_metadata,
        custom_fields={
            "artifact_path": manifest.artifact_name,
            "artifact_hash": manifest.artifact_sha256,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Software Factory v2 - Worker process"
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to config YAML (not yet implemented)",
    )
    parser.parse_args()
    config = FactoryConfig()
    from factory.claude_code_channel import ClaudeCodeChannel

    channel = ClaudeCodeChannel(config)
    run_worker(config, channel)


if __name__ == "__main__":
    main()
