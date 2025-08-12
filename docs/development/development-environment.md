# Baserow's dev environment

The dev environment runs Baserow services with source code hot reloading enabled. It
also runs the backend django server and web-frontend nuxt server in debug and
development modes. It is recommended that you use [dev.sh](../development/dev_sh.md)
found in the root of the Baserow repo.

## Further reading

- See [running the dev environment](running-the-dev-environment.md) for a
  step-by-step guide on how to set-up the dev env.
- See [baserow docker api](../installation/install-with-docker.md) for more detail on how
  Baserow's docker setup can be used and configured.
- See [dev.sh](dev_sh.md) for further detail on the CLI tool for managing
  the dev environment.
- See [intellij setup](intellij-setup.md) for how to configure Intellij 
  to work well with Baserow for development purposes.
- See [feature flags](feature-flags.md) for how Baserow uses basic feature flags for
  optionally enabling unfinished or unready features.
- See [vscode setup](vscode-setup.md) for how to configure Visual Studio Code
to work well with Baserow for development purposes.

## Fixing git blame

A large formatting only commit was made to the repo when we converted to use the black
auto-formatter on April, 12 2021. If you don't want to see this commit in git blame, you
can run the command below to get your local git to ignore that commit in blame for this
repo:

```bash
$ git config blame.ignoreRevsFile .git-blame-ignore-revs
```
