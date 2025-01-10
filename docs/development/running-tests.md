# Running tests

## Backend

The standard way to run tests in the backend is to start and attach to the
containers as described in [running-the-dev-environment.md](running-the-dev-environment.md),
and then run the command `make test` or `make test-parallel`.

For the tests, the configuration in `config.settings.tests` is used, which sets
some base variables and ignores all environment variables set in the `.env`
file. The `.env` file is normally used to change the default values for running
Baserow in production or development mode.

### Running tests outside the backend container

If you want to run the tests outside of the backend container, you need to
create a Python virtual environment and install all the requirements listed in
`requirements/base.txt` and `requirements/dev.txt`.

You also need to provide the environment variables to connect to the database,
since by default `test.py` will use `"db"` as `DATABASE_HOST`, which is only
valid inside the Docker network. Since `test.py` will ignore every environment
variable in your shell or in the `.env` file, you will need to create a file
named `.env.testing` in the backend directory and set the necessary environment
variables to run the tests. At a minimum, you need to set `DATABASE_HOST` to
point to the database. If the dev environment is running without modifications
with [dev.sh](dev_sh.md), you should only add a line with
`DATABASE_HOST=localhost` to point to the port exposed locally by Docker
instead of the default "db".

Your test env file will look something like this:

```env
# backend/.env.testing
DATABASE_HOST=localhost
```

If `.env.testing` is already used within the container with custom variables to
test specific scenarios, you can also create a file with another name in the
backend directory and export it as an environment variable before running the
tests:

```sh
export TEST_ENV_FILE='.env.local-testing'
```

At this point, you can run `make test` or `make test-parallel` from your shell
outside the containers in the backend directory, and everything should work as 
expected.