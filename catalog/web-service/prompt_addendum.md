This module is part of a **web-service deliverable**. Its acceptance criteria
describe HTTP behavior (methods, paths, request bodies, and response status
codes), so the artifact must satisfy them **over HTTP**, not as plain function
calls.

**One service, one shared `app` (walking-skeleton model).** The whole service has
a single module-level ASGI application named `app`. The conformance gate loads it
as `app:app`. Modules do **not** each stand up their own separate service —
they share one `app`:

- **The substrate module** (the dependency-root module that owns shared
  infrastructure — the datastore/connection and the boot health route; it carries
  `AC-BOOT-01`) **defines and owns `app`**. It creates the ASGI application object
  and exposes it as a module-level binding.
- **A feature module** (one that owns specific endpoint ACs) **imports the shared
  `app` from its substrate dependency and registers its own routes onto it**, then
  re-exposes `app` as a module-level binding so its tests and the integrator see
  the app with this module's routes attached. A feature does **not** create a new
  application object.

Identify which you are from your spec and dependencies: if your spec describes
shared schema/connection/utilities for other modules (or you carry `AC-BOOT-01`),
you are the substrate; otherwise you are a feature that registers onto the
substrate's `app`.

**Contract shape — a route table on the shared app.**

- **`app` must be an importable binding, not a bare annotation.** Downstream tests
  do `from interface import app` and use it as a value. In the locked interface
  stub write `app = ...` (an assigned Ellipsis placeholder) — **not** an
  annotation-only `app: SomeType`, which creates no importable name and breaks test
  collection. The implementer replaces the placeholder with the real app (substrate)
  or with the substrate's app plus this module's routes (feature).
- Your module registers exactly the **routes its ACs require**. For each route the
  contract is: HTTP **method**, **path** (including path parameters), the **request
  schema**, the **response schema**, and the **HTTP status code(s)** — success and
  every error case the ACs name (e.g. 201, 307, 404, 422).
- **Input validation and error formatting are part of the contract.** An AC that
  requires "HTTP 422 for an invalid body" is satisfied only by a route that returns
  that status and body — never by a function returning an `Error` dataclass for a
  caller to translate.
- Persistence ACs ("returns the stored links", "offset/limit slice real data") must
  read the real datastore, not fabricated in-memory values.

**Framework is your choice.** Any ASGI framework (FastAPI, Starlette, Quart, or a
hand-written ASGI app) is acceptable — the contract is the shared ASGI `app` and
the routes registered on it, not a named library. Nothing is graded on which
framework you pick; use its native route-registration mechanism.

**Per role:**

- *Interface architect*: lock the route table this module contributes (typed
  request/response models + declared routes with status codes) plus the `app`
  binding. A `.pyi` of plain functions does **not** capture an HTTP deliverable.
- *Test author*: exercise the ACs **through an in-process ASGI client**
  (`httpx.ASGITransport` against `app`). This is in-process, not external network
  or DB access — required here, and not a "no live network" violation. Assert on
  HTTP **status codes and response bodies**. Write plain `async def test_...`
  functions — the gate runs them automatically (asyncio mode); do not add
  `@pytest.mark.asyncio` or an `anyio_backend` fixture.
- *Implementer*: substrate — create `app` and the boot route, own the datastore.
  Feature — import the substrate's `app`, register your routes on it, re-expose
  `app`. You may add an ASGI framework dependency and must expose the module-level
  `app`, notwithstanding the default "stdlib only / no new public symbols" rule.
