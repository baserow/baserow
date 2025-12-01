# ./dev.sh

`dev.sh` is a helper bash script which makes working with baserow's development
environment a breeze.

By default, running `./dev.sh` will start the dev env, attach into the running
containers and make sure the containers are running as your actual user.

Additionally, Baserow's dev containers are especially configured to make the attaching
experience smooth and useful. In the per container tabs opened by using `./dev.sh`:

* The output of docker logs will be shown at the top letting you see everything that has
  happened in the container so far.
* You can press ctrl-c to stop the process running inside the container leaving you in a
  bash session inside the container, but not stop the container itself. This is useful
  as you often want to stop the dev server, run a management command and quickly restart
  it.
* The bash session you are left in after pressing ctrl-c will have a history populated,
  so you can press up to get the command that the container was running before you
  pressed ctrl-c!

## Examples of ./dev.sh usage:

```bash
$ ./dev.sh # same as the up command above but also ensures the containers run as the running user!
$ ./dev.sh --build # ups and rebuilds
$ ./dev.sh restart # stops and then ups
$ ./dev.sh restart --build # stops, builds, ups
$ ./dev.sh build_only # just builds
$ ./dev.sh dont_attach # does not create tabs and attach to the containers at the end
$ ./dev.sh dont_attach restart --build # You can combine multiple arguments like so
$ ./dev.sh dont_migrate # ups but doesn't migrate automatically on startup
$ ./dev.sh dont_migrate dont_sync dont_attach restart --build # even more flags!
$ ./dev.sh run backend manage migrate
# Any commands found after the last `./dev.sh` command will be passed to the `docker-compose up` call made by dev.sh
# This lets you say do --build on the end or any other docker-compose commands using dev.sh!
$ ./dev.sh restart {EXTRA_COMMANDS_PASSED_TO_UP}  
$ ./dev.sh down # downs the env
$ ./dev.sh kill # kills (the old stop_dev.sh)
# WARNING: restart_wipe will detail ALL volumes associated with that environment 
# permanently. 
$ ./dev.sh restart_wipe --build
# Dev.sh also supports running different Baserow setups:
# The local flag runs the non-dev production images with no code mounting + hot 
# reloading etc. It however builds fresh new images from your local repo.
$ ./dev.sh local restart --build
$ ./dev.sh all_in_one restart --build
$ ./dev.sh cloudron restart --build
$ ./dev.sh heroku restart --build
# Bind to different ports on the host manage incase you are already running them and they clash! (also works with just docker-compose up)
$ POSTGRES_PORT=5555 ./dev.sh
```

## Why ./dev.sh ensures the containers run as you

In dev mode Baserow's source control directories are mounted from your local git repo
into the containers. By mounting these the containers will see source code changes and
automatically rebuild. However, if the containers are not running as your actual user
then the containers might accidentally change the ownership or create files owned by the
user running inside the container. So by running the containers as your user there is no
chance that your source control directories will have file ownership problems.
Additionally, it
is [best practice](https://medium.com/@mccode/processes-in-containers-should-not-run-as-root-2feae3f0df3b)
to not run Docker containers as the default root user.

## Customizing the default ./dev.sh behavior

It is possible to change the way `./dev.sh` script behaves by using built-in pre and post hooks. To do so, place your code in new local files `.local/pre_devsh_hook.sh` or `.local/post_devsh_hook.sh` depending on your needs. These files will be sourced and executed every time the `./dev.sh` script runs.

Consider the following example to opt-out of some behavior when starting Baserow for development:

```bash
# inside .local/pre_devsh_hook.sh
sync_templates=false  # Skips template syncing on startup
e2e_tests=false  # Won't start end to end tests
```
