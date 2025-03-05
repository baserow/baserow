# Running Tests

## Backend

To run backend tests, start and attach to the backend container as described in 
[running-the-dev-environment.md](running-the-dev-environment.md). Once inside 
the container, execute `make test` or `make test-parallel` to run the tests.

The tests use the `config.settings.tests` configuration, which sets base 
variables and ignores environment variables in the `.env` file. The `.env` file 
is intended for production or development mode.

### Customize Test Settings

You can customize test settings by creating a `.env.testing` file in the 
backend directory. For example:

```env
# backend/.env.testing
BASEROW_MAX_FIELD_LIMIT=1
```

### Migrations and database setup

By default, `BASEROW_TESTS_SETUP_DB_FIXTURE` is considered `on` in the
`config.settings.tests` configuration. This means that the database will be 
set up without running the migrations, but only installing the database 
formulas needed for the tests. This is done to speed up the test setup 
process.

If you want to run the migrations, you can run 
`BASEROW_TESTS_SETUP_DB_FIXTURE=off pytest` to run them all. This is useful 
when you want to test the migrations and you don't care about the speed of 
the test setup.

If you want to install the custom formula pgSQL functions only once and then 
reuse the database between tests, you can run 
`BASEROW_TESTS_SETUP_DB_FIXTURE=off pytest --no-migrations --reuse-db`. 

You can even omit `--no-migrations` to apply any new migrations coming from 
the current branch to avoid recreating the database from scratch.


### Running Tests Outside the Backend Container

To run tests outside the backend container, follow these steps:

1. Create a Python virtual environment. See [supported](../installation/supported.md) 
   to determine the supported version of Python.
2. From the backend directory, install the required packages with 
   `pip install requirements/base.txt` and `pip install requirements/dev.txt`.
3. Set environment variables to connect to the database. Create a 
    `.env.testing-local` file in the backend directory. At a minimum, set 
    `DATABASE_HOST` to `localhost` since the default value of `db` is only valid 
    inside the docker network.

```env
# backend/.env.testing-local
DATABASE_HOST=localhost
```

4. Export the `TEST_ENV_FILE` variable to specify the environment file:

```sh
export TEST_ENV_FILE='.env.testing-local'
```

5. Run `make test` or `make test-parallel` from your shell outside the 
    containers in the backend directory.
