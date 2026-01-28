# Directory structure

One of the things you will notice it that all the files and directories are in the
same repository. This makes it easier to setup a demo and development environment and
all the changes can be put in a single merge request.

In the root you will find three folders `backend`, `docs` and `web-frontend`. You will
also notice some files that are related to the whole project like an editor config
file, continuous integration config, changelog, docker-compose yaml files and a readme.
In the following topics we will zoom in on the directories.

## backend

In the backend directory you will find some files that are related only to the backend.
This whole directory is also added to the backend container.

* `pyproject.toml`: Python project configuration including dependencies managed by uv.
* `uv.lock`: lockfile for reproducible dependency installation.
* `.flake8`: contains the flake8 linter configuration.
* `baserow`: is actually a python file, that just calls the management.py file in the
  source directory. This file is registered as a command via the `pyproject.toml`. When
  someone adds Baserow as a dependency they can use the command `baserow migrate` which
  is the same as `python src/baserow/manage.py migrate`.
* `Dockerfile`: Builds an image containing just the backend service, build with
   `--target dev` to instead get a dev ready image.
* `justfile`: contains commands to install dependencies, run the linter, run tests,
  and start development servers.
* `pytest.ini`: pytest configuration when running the tests.

### src

The src directory contains the full source code of the Baserow backend module.

* `api`: is a Django app that exposes Baserow via a REST API. Even though it is an
  optional app it is installed by default. It's highly recommended to use this package.
  It contains several directories each with their urls, views, serializers, and errors
  related to a specific part. For example, the workspaces and application both have their
  own directory. There are also several modules that contain some generic classes,
  functions, and decorators that are reused throughout the code. The `urls.py` module
  is included by the root url config under the namespace `api`.
* `config`: is a module that contains base settings and some settings that are for
   specific environments. It also contains the root url config that includes the api
   under the namespace `api`. There is
   also a wsgi.py file which can be used to expose the applications.
* `contrib`: contains extra apps that can be installed. For now it only contains the
  backend part of the database plugin. This app is installed by default, but it is
  optional.
* `core`: is a required app that is installed by default. It contains some abstract
  concepts that are reused throughout the backend. It also contains the code for the
  workspace and application concepts that are at the core of Baserow. Of course there are
  also helper classes, functions, and decorators that can be reused.
* `manage.py`: the Django manage.py file to execute management commands.

### tests

The tests folder contains a baserow folder which matches the directory structure of
the `src/baserow` folder. Instead of it containing the source files it contains
the tests. The files always start with `test_` to ensure they are picked up by
pytest. They always end with the name of the related file in the source directory.

There is also a fixtures directory which contains modules with classes that have small
helpers to create data. For example if you quickly want to write a test related to a
database table text field you can quickly create one by doing something like in your
test.

```python
def test_something_important(data_fixture):
    # A table, database and workspace have also been created because the text field depends
    # on them.
    field = data_fixture.create_text_field()
```

## web-frontend

In the web-frontend directory you will find some files that are related only to the
web frontend. This whole directory is also added to the web-frontend container.

* `.babelrc`: contains the configuration for the babel compiler.
* `.eslintignore`: a text file containing directories that must be ignored by eslint.
* `.eslintrc.js`: the configuration for the eslint linter.
* `.prettierrc`: configuration for prettier.
* `.stylelintrc`: configuration for stylelint which lints the scss code.
* `Dockerfile`:  Builds an image containing just the web-frontend service, build with
  `--target dev` to instead get a dev ready image.
* `intellij-idea.webpack.config.js` a webpack config file that can be used by Intellij
  iDEA. It adds the correct aliases for the editor.
* `jest.config.js`: config file for running the tests with JEST.
* `justfile`: contains commands to install dependencies, run the linter, and run
  the tests.
* `nuxt.config.js`: base Nuxt config for the development environment.
* `package.json`: main package config including all the dependencies for the
  web-frontend.
* `yarn.lock`: auto generated file containing a list of the dependencies installed via
  yarn.

### config

The config directory contains some base Nuxt settings and some settings for specific
environments. For example, in the development environment the eslint loader is added to
webpack.

### modules

All the modules follow the common directory structure of Nuxt. More information can be
found in the
[Nuxt documentation about the directory structure](https://nuxtjs.org/guide/directory-structure/).

### tests

At the moment there are only a few tests related to the web-frontend. Because the tests
aren't maintained at this point, the directory structure is off. The specs should be in
the matching modules directory.

## docs

The docs folder contains markdown files with the full developer documentation of
Baserow. The contents of these files are automatically placed on
https://baserow.io/docs.

## plugin-boilerplate

Contains a cookiecutter boilerplate for a Baserow plugin. More information can be found
on the [plugin boilerplate page](../plugins/boilerplate.md).

## media

Contains a nginx based docker image which is used in Baserow's docker setup to serve
any uploaded user files. This is needed as Django will not serve media files when
not in debug mode and instead requires you to run your own web server to serve these
assets.
