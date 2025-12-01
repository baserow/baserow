# Running the dev environment

If you want to contribute to Baserow you need to setup the development environment on
your local computer. The best way to do this is via `docker-compose` so that you can
start the app with the least amount of hassle.

### Quickstart

If you are familiar with git and docker-compose run these commands to launch Baserow's
dev environment locally, otherwise please start from the Installing Requirements section
below.

```bash
$ git clone --branch develop git@github.com:baserow/baserow.git
# Our supplied ./dev.sh script wraps docker-compose setting the correct env vars for 
# you to get hot code reloading working well.
$ ./dev.sh 
# Run ./dev.sh help for further details.
$ ./dev.sh help
```

## Installing requirements

If you haven't already installed docker and docker-compose on your computer you can do
so by following the instructions on https://docs.docker.com/desktop/ and
https://docs.docker.com/compose/install/.

> Docker version 19.03 is the minimum required to build Baserow. It is strongly
> advised however that you install the latest version of Docker available.
> Please check that your docker is up to date by running `docker -v`.

You will also need git installed which you can do by following the instructions on
https://www.linode.com/docs/development/version-control/how-to-install-git-on-linux-mac-and-windows/
.

Once you have finished installing all the required software you should be able to run
the following commands in your terminal.

```bash
$ docker -v
Docker version 20.10.6, build 370c289
$ docker-compose -v
docker-compose version 1.26.2, build eefe0d31
$ git --version
git version 2.24.3 (Apple Git-128)
```

If all commands return something similar as described in the example, then you are ready
to proceed!

## Starting the dev environment

> If you run into any issues starting your development environment feel free to contact
> us via the form on https://baserow.io/contact.

For example purposes I have created a directory in my home folder named `baserow`. You
can of course follow the steps in any directory, but in this tutorial I will assume the
working directory is `~/baserow`.

First we have to clone the repository. Execute the following commands to clone the
master branch. If you are not familiar with git clone, this will download a copy of
Baserow's code to your computer.

```
$ cd ~/baserow
$ git clone --branch master https://github.com/baserow/baserow.git
Cloning into 'baserow'...
...
$ cd baserow
```

Now that we have our copy of the repo and have changed directories to the newly
created `baserow`, we can bring up the containers. You just have to execute the
docker-compose command using the `docker-compose.yml` file. It might take a while for
the command to finish, this is because the images have to be built from scratch.

```
$ ./dev.sh 
Building backend
...
Starting db    ... done
Starting redis    ... done
Starting backend    ... done
Starting web-frontend   ... done
```

Your dev environment is now running, the database has been automatically migrated for
you and the baserow templates have been synced. You can now visit http://localhost:3000
to sign up and login to your Baserow.

## Looking at the web api

Baserow's backend container exposes a rest API. Find the API spec for your local version
of Baserow at http://localhost:8000/api/redoc/ . To check that it is working correctly
when you visit http://localhost:8000/api/workspaces/ in a browser you should see the error
"Authentication credentials were not provided." as no JWT was provided.

## Attaching to the dev environment

The dev environment consists of a number of docker containers, see:

If you use `./dev.sh` by default it will attempt to open tabs in your terminal and
attach to the running baserow containers. Otherwise you can do so manually by running
the following commands:

```bash
$ # Run the commands below to connect to the various different parts of Baserow
$ docker attach backend
$ docker attach celery 
$ docker attach web-frontend
```

When attached you can press CTRL-C to end the current containers main process. However
unlike normal docker containers this one will not exit immediately but instead present
you with a bash terminal. In this terminal you can then run any admin commands you wish
or inspect the state of the containers. Simply press up and go through the containers
bash history to get the original command to restart the containers main process.

## Other useful commands

Below is a quick example of some of the more common useful operations and commands:

```bash
$ # View the logs 
$ docker-compose logs 
$ # Migrate
$ ./dev.sh run backend manage migrate
$ # Restart and Build 
$ ./dev.sh restart --build 
```

## Keep the servers running

Both the web-frontend and backend containers need to keep running while you are
developing. They also monitor file changes and update automatically, so you don't need
to worry about reloading. Go and make some changes yourself. You should see the result
right away.

## Working with Docker and Django

For further reading on how to work with docker containers and django check out:

- [django's getting started tutorial](https://docs.djangoproject.com/en/3.1/intro/tutorial01/)
- [docker's getting started tutorial](https://docs.docker.com/get-started/)
- [docker's cli reference](https://docs.docker.com/engine/reference/run/)
- [docker composes reference](https://docs.docker.com/compose/)

## Baserow further reading

- See [introduction](../technical/introduction.md) for more details on Baserow's
  architecture.
- See [baserow docker api](../installation/install-with-docker.md) for more detail on how
  Baserow's docker setup can be used and configured.
- See [dev.sh](dev_sh.md) for further detail on what dev.sh does and why
