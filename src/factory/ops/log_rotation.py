from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from factory.config import OpsConfig

_ops_log = logging.getLogger("factory.ops.log_rotation")


def configure_log_rotation(
    log_file: str | Path,
    config: OpsConfig | None = None,
    logger: logging.Logger | None = None,
) -> RotatingFileHandler:
    cfg = config or OpsConfig()
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        str(path),
        maxBytes=cfg.log_max_size_bytes,
        backupCount=cfg.log_backup_count,
    )

    target_logger = logger or _ops_log
    target_logger.addHandler(handler)

    _ops_log.debug(
        "log_rotation_configured path=%s max_bytes=%d backup_count=%d",
        path,
        cfg.log_max_size_bytes,
        cfg.log_backup_count,
    )

    return handler
