# Zed Setup

This guide explains how to use [Zed](https://zed.dev) with Baserow, including the
Python/Django debugger configurations that ship with the repo.

## Prerequisites

- [just](https://github.com/casey/just)
- [uv](https://github.com/astral-sh/uv)
- A local backend virtualenv created by `just b init` (lives at `.venv/`)

## Apply the standard config

From the repo root run:

```bash
./config/zed/apply_standard_baserow_zed_config.sh
```

This copies `config/zed/.zed/` into `<repo>/.zed/`, giving you:

- `.zed/debug.json` — Debug Adapter Protocol (Debugpy) configurations
- `.zed/settings.json` — Python LSP (`pyright` + `ruff`) extra paths

You can also copy the files manually if you prefer to merge by hand.

> **Personal customisations** — `.zed/` at the repo root is git-ignored, so any
> changes you make after running the script are private to your machine.  Add
> extra env vars, additional launch configs, or personal secrets directly to
> `.zed/debug.json` without worrying about committing them.

## Debug configurations

Open the debug panel in Zed (`cmd-shift-d` / `ctrl-shift-d`) or run the
`debugger: start` command, then pick one of:

### backend: django runserver (launch)

Starts the Django dev server single-process under Debugpy.  Breakpoints set in
view/model code are hit on the next matching request.

> **Why `--noreload`?**  Django's autoreloader forks a child process to handle
> HTTP requests while the parent watches source files.  Debugpy attaches to the
> parent, so without `--noreload` breakpoints in request-handling code are never
> reached.  The trade-off is that you must **restart the debug session manually**
> after editing Python source files.
>
> If you need hot-reloading, use the attach config below instead.

### backend: django (attach to :5678)

Attaches to an already-running Django process that is listening for a Debugpy
client on port 5678.  This is the **recommended approach for local development**
because breakpoints work correctly *and* the autoreloader stays enabled.

**Local venv workflow:**

```bash
BASEROW_BACKEND_DEBUGGER_ENABLED=1 just b run-dev-server
```

With that env var set, `manage.py` calls `debugpy.listen(5678)` inside the
`RUN_MAIN` child process — the process that actually handles HTTP requests.
Once you see the server start up, launch this config from the Debug panel to
attach.

**Docker dev env workflow:**

```bash
just dc-dev up -d
```

The backend container already maps container port 5678 → host 5678.  Set
`BASEROW_BACKEND_DEBUGGER_ENABLED=1` in your `docker-compose.override.yml` and
then attach as above.

### backend: celery worker (launch)

Runs a Celery worker under Debugpy in single-threaded mode (`--pool=solo`).
Breakpoints set inside task functions are hit when a task is dispatched.

> `--pool=solo` is required for the same reason as `--noreload` above — pool
> strategies that use forked sub-processes put the task execution in a child
> that Debugpy is not attached to.

Queues consumed: `celery`, `export`, `automation_workflow`.

### backend: pytest current file

Runs `pytest` on the file that is currently open and focused in the editor.
Make sure the test file is the active tab before launching this config.

### backend: pytest all (with coverage)

Runs the full core + premium + enterprise test suite with coverage, writing an
XML report to `html_coverage/cov.xml`.

> `-n=auto` parallelises execution across all CPU cores, which significantly
> reduces wall-clock time but **disables Debugpy breakpoints**.  Remove that
> flag from `.zed/debug.json` if you need to step through code during a full
> run.

## Interpreter path

All launch configs expect the virtualenv at `.venv/bin/python` (created by
`just b init`).  If your interpreter lives elsewhere, update the `python` field
in `.zed/debug.json`.

## See also

- `docs/development/debugging.md` — `snoop`, `django-silk`, `flower`, etc.
- `docs/development/vscode-setup.md` — equivalent VSCode setup
- `docs/development/running-tests.md` — full test command reference