# Baserow's dev environment

The dev environment runs Baserow services with source code hot reloading enabled. It
also runs the backend django server and web-frontend nuxt server in debug and
development modes.

## Getting started

The recommended way to run the dev environment is using [just](justfile.md) commands:

- **Docker development**: `just dc-dev up -d` - runs all services in Docker containers
- **Local development**: `just dev` - runs services natively with Docker only for db/redis

See [running the dev environment](running-the-dev-environment.md) for a complete
step-by-step guide.

## Further reading

- See [running the dev environment](running-the-dev-environment.md) for a
  step-by-step guide on how to set-up the dev env.
- See [justfile reference](justfile.md) for all available `just` commands.
- See [baserow docker api](../installation/install-with-docker.md) for more detail on how
  Baserow's docker setup can be used and configured.
- See [intellij setup](intellij-setup.md) for how to configure Intellij
  to work well with Baserow for development purposes.
- See [feature flags](feature-flags.md) for how Baserow uses basic feature flags for
  optionally enabling unfinished or unready features.
- See [vscode setup](vscode-setup.md) for how to configure Visual Studio Code
  to work well with Baserow for development purposes.

> **Note**: The older `dev.sh` script is deprecated. See [dev.sh](dev_sh.md) for
> documentation on the legacy script if needed.

## Fixing git blame

A large formatting only commit was made to the repo when we converted to use the black
auto-formatter on April, 12 2021. If you don't want to see this commit in git blame, you
can run the command below to get your local git to ignore that commit in blame for this
repo:

```bash
$ git config blame.ignoreRevsFile .git-blame-ignore-revs
```
