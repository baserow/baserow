# VSCode Setup

This guide walks you through a first time VScode setup for Baserow for developers. It
will ensure you can run and debug all tests and also enable all the relevant linters and
automatic style fixers to make your life as easy as possible.

> This guide assumes you have a basic understanding of git, python, virtualenvs,
> postgres and command line tools.

## Prerequisites

Install the following tools:
- [just](https://github.com/casey/just) - command runner
- [uv](https://github.com/astral-sh/uv) - Python package manager

## Setup Steps

1. First checkout a fresh copy of Baserow: `git clone git@github.com:baserow/baserow.git`
   (or your personal fork of the project)
1. `cd baserow`
1. `./config/vscode/apply_standard_baserow_vscode_config.sh`
    1. Type `Y` and hit enter to apply the standard Baserow config
1. Open VSCode and on the "Welcome to VSCode" screen click the "Open" button
   and open the baserow folder you cloned above.
1. Make sure you have installed / enabled the Python VSCode plugin.
1. Now we will create a Python virtual environment and configure VSCode to use it to run tests
   and linters:
    1. Initialize the backend (creates venv and installs dependencies):
       ```bash
       just b init
       ```
       This creates a virtualenv at `.venv/` in the project root.
    2. Then you will most likely need to select it as default interpreter for the project:
         1. Type: Ctrl + Shift + P or open the command palette
         1. Type: Python: select interpreter
         1. Find and select your virtualenvs `bin/python` executable (`.venv/bin/python`)
    3. If do not see the python tests in the testing menu:
         1. Type: Ctrl + Shift + P or open the command palette
         1. Type: Python: Configure Tests
1. Install and get a postgresql database running locally:
    1. The easiest way is to use Docker:
       ```bash
       just dc-dev up -d db redis
       ```
    2. Or install PostgreSQL locally:
       [https://www.postgresql.org/docs/11/tutorial-install.html](https://www.postgresql.org/docs/11/tutorial-install.html)
    3. If running PostgreSQL locally, create a baserow user:
        ```sql
        CREATE USER baserow WITH ENCRYPTED PASSWORD 'baserow';
        ALTER USER baserow CREATEDB;
        ```
1. Now you should be able to run the backend python tests from the testing menu, try
   run `backend/tests/baserow/core/test_core_models.py` for instance.
1. Now lets set up your frontend dev by changing directory to `baserow/web-frontend`
1. Use [nvm](https://github.com/nvm-sh/nvm) or [fnm](https://github.com/Schniz/fnm) to install the correct version of `node`.
   To determine the version of Node.js to use, see the `runtimeVersion` inside the
   `launch.json` file. E.g. if the version is `v16.15.0`, you can install it with:
   `nvm install v16.15.0` and then enable it with `nvm use v16.15.0`. Alternatively,
   see `baserow/docs/installation/supported.md` to determine the supported version
   of Node.js to use.
1. Install `yarn` globally: `npm install -g yarn`
1. Now run `just f install` to install dependencies (or `yarn install` directly).
1. Select "Trust Project" if you see an VSCode popup after running yarn install
1. If you do not see Jest tests in the testing menu:
   1. Type: Ctrl + Shift + P or open the command palette
   1. Type: Jest: Start All Runners
1. Confirm you can run a web-frontend unit test from vscode

# Recommended Plugins

You can use the VSC Export & Import to install what is inside `config/vscode/vsc-extensions.txt`.
Otherwise, you can manually install:

1. Python
1. Volar
1. Eslint
1. Gitlab Workflow
1. Gitlens
1. Jest
1. SCSS Formatter
1. Stylelint
1. Mypy
1. Docker
1. Coverage Gutters
