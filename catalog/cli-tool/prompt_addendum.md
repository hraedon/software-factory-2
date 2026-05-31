This module is a **command-line tool**. Its acceptance criteria describe CLI
behavior (arguments, stdout/stderr output, and exit codes), and the artifact must
satisfy them through that surface.

**Contract shape:**

- The module exposes a `main()` function as its entry point and parses arguments
  with the stdlib `argparse`.
- The contract for each AC is: the **arguments/flags** it consumes, the **stdout**
  (or file) output it produces, and the **process exit code** — `0` on success,
  non-zero with a message on `stderr` for each error case the ACs name.
- *Test author*: drive `main()` with argument lists and assert on captured
  stdout/stderr and exit code (`capsys` / `SystemExit`); this is in-process and does
  not require live network or DB access.
- *Implementer*: implement `main()` so those tests pass over the CLI surface.
