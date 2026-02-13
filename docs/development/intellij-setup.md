# IntelliJ Setup

This guide walks you through a first time Intellij setup for Baserow for developers. It
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
1. `cd baserow`
1. `./config/intellij/apply_standard_baserow_intellij_config.sh`
    1. Type `Y` and hit enter to apply the standard Baserow config
1. Open Intellij and on the "Welcome to IntelliJ IDEA" screen click the "Open" button
   and open the baserow folder you cloned above.
1. Make sure you have installed / enabled the
   [Python IntelliJ plugin](https://plugins.jetbrains.com/plugin/631-python).
1. Now we will create a Python virtual environment and configure IntelliJ to use it to run tests
   and linters:
    1. Initialize the backend (creates venv and installs dependencies):
       ```bash
       just b init
       ```
       This creates a virtualenv at `.venv/` in the project root.
    2. Now back in Intellij, press F4 or right-click on the top level baserow folder and
       select `module settings`:
        1. Make sure the `backend` module SDK is set to the python virtualenv you just
           made (`.venv/bin/python`).
        1. There will most likely be an existing `Python 3.14 (baserow)` virtualenv SDK
           which is red. Delete this first.
        1. Then you will most likely need to add it as a new SDK by navigating to
            1. F4 → SDK
            1. click +
            1. Add New Python SDK
            1. Existing Interpreter
            1. Find and select your virtualenvs `bin/python` executable (`.venv/bin/python`)
            1. call this new SDK `Python 3.14 (baserow)` so you don't make an accidental
               change to the `backend.iml` file:
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
1. Now you should be able to run the backend python tests, try
   run `backend/tests/baserow/core/test_core_models.py` for instance.
1. Now lets set up your frontend dev by changing directory to `baserow/web-frontend`
1. Now run `just f install` (or `yarn install` directly). If you do not have yarn available
   check out and install a node version manager like [nvm](https://github.com/nvm-sh/nvm) or
   [fnm](https://github.com/Schniz/fnm) and follow the
   [Yarn installation instructions](https://yarnpkg.com/getting-started/install)).
   See `baserow/docs/installation/supported.md` to determine the supported version of
   Node.js to use.
1. Select "Trust Project" if you see an IntelliJ popup after running yarn install
1. Open your settings, search for and open the `Node.js and NPM` category and ensure the
   Node interpreter is pointing to the desired node executable
1. Confirm you can run a web-frontend unit test from intellij
1. Open settings and search for eslint, make sure you have switched
   to `Manual ESLint configuration`, have set the `ESlint package` to to `eslint` sub
   folder in the `node_modules` created by the
   previous `yarn install` (`baserow/web-frontend/node_modules/eslint`)

# Recommended Plugins

1. [https://plugins.jetbrains.com/plugin/14321-blackconnect](https://plugins.jetbrains.com/plugin/14321-blackconnect)
    1. Auto runs black over changed files. Setup a blackd daemon that runs on startup
       for lowest friction.
1. [Database Navigator](https://plugins.jetbrains.com/plugin/1800-database-navigatorkey)
1. [IntelliVue](https://plugins.jetbrains.com/plugin/12014-intellivue)
1. [Key Promoter X](https://plugins.jetbrains.com/plugin/9792-key-promoter-x)
1. [Vue.js](https://plugins.jetbrains.com/plugin/9442-vue-js)
