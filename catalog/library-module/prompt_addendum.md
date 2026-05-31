This module is an **importable library**. Its acceptance criteria are satisfied by
calling its public functions and classes directly — there is no HTTP or CLI surface.

**Contract shape:**

- The contract is the typed public API the ACs require: function and class
  signatures, return types, and the error values/exceptions each AC names. This is
  the default `.pyi` contract shape.
- The module has **no** CLI entry point and **no** server `app`. Public API is
  exposed via `__all__`.
- *Test author*: call the public API directly and assert on return values and
  raised errors — no network or DB access.
- *Implementer*: implement the locked signatures so those tests pass.
