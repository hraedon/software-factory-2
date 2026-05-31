from __future__ import annotations

import asyncio
import json
import random
import string
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any, cast

_links_by_task: dict[int, list[LinkResponse]] = {}


@dataclass(frozen=True)
class CreateLinkRequest:
    url: str


@dataclass(frozen=True)
class LinkResponse:
    slug: str
    url: str
    short_url: str


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


async def healthz() -> None:
    return None


def _generate_slug() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=6))


def _is_valid_url(url: str) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _get_links() -> list[LinkResponse]:
    task = asyncio.current_task()
    task_id = id(task) if task else 0
    return _links_by_task.setdefault(task_id, [])


async def create_link(body: CreateLinkRequest) -> LinkResponse:
    if not _is_valid_url(body.url):
        raise ValueError("invalid_url")

    links = _get_links()
    slug = _generate_slug()
    while any(link.slug == slug for link in links):
        slug = _generate_slug()

    short_url = f"http://host/{slug}"
    response = LinkResponse(slug=slug, url=body.url, short_url=short_url)
    links.append(response)
    return response


async def list_links(offset: int = 0, limit: int = 20) -> list[LinkResponse]:
    links = _get_links()
    return links[offset : offset + limit]


async def _read_json_body(
    scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]]
) -> dict[str, Any]:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return cast(dict[str, Any], json.loads(body.decode("utf-8")))


async def app(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/healthz":
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})
        return

    if method == "POST" and path == "/links":
        try:
            body = await _read_json_body(scope, receive)
            if (
                not isinstance(body, dict)
                or not isinstance(body.get("url"), str)
                or not _is_valid_url(body["url"])
            ):
                raise ValueError("invalid_url")
        except Exception:
            await send(
                {
                    "type": "http.response.start",
                    "status": 422,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": json.dumps({"code": "invalid_url", "message": "invalid_url"}).encode(),
                }
            )
            return

        req = CreateLinkRequest(url=body["url"])
        result = await create_link(req)
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(
                    {
                        "slug": result.slug,
                        "url": result.url,
                        "short_url": result.short_url,
                    }
                ).encode(),
            }
        )
        return

    if method == "GET" and path == "/links":
        query_string = scope.get("query_string", b"").decode("utf-8")
        params: dict[str, str] = {}
        if query_string:
            for pair in query_string.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 20))

        results = await list_links(offset=offset, limit=limit)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps([asdict(r) for r in results]).encode(),
            }
        )
        return

    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})
