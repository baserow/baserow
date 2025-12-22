# Creating A Plugin

> Check out our [Plugin community sub-forum](https://community.baserow.io/c/plugins/17)
> for community made plugins and further discussion.

In this guide we dive into how to create a Baserow plugin from scratch, give you example
plugins to get inspiration from and discuss how to publish your plugin.

## Initialize your plugin from the official template

We highly recommend using
the [Step by step tutorial on plugin creation using the plugin boilerplate](./boilerplate.md)
which will setup a basic Baserow plugin ready for you to start working on.

To instantiate the template, execute the following commands:

```sh
$ cd ~/baserow
$ pip install cookiecutter
$ cookiecutter gl:baserow/baserow --directory plugin-boilerplate
```

## Get inspiration from our examples

Additionally, we have created two example plugins to show plugin authors how to do
common things with a plugin.

### [Baserow Geo Plugin](https://gitlab.com/nigel_baserow/baserow_geo_plugin/)

The [Geo plugin](https://gitlab.com/nigel_baserow/baserow_geo_plugin/) is an example
plugin which adds a new "Point" field type. It shows how to:

* Install and enables a postgres extension (only when Baserow is running in the
  all-in-one image when using an embedded database)
* Install extra system packages using apt-get
* Add custom backend python and frontend node dependencies
* Add a new field type, with custom components and scss

### [Baserow Example Formula Plugin](https://gitlab.com/nigel_baserow/baserow_example_formula_plugin/)

The [Example formula plugin](https://gitlab.com/nigel_baserow/baserow_example_formula_plugin)
adds a new formula function called `timezone`. It shows how to :

* Add a new formula function to Baserow
* Use a custom plpgsql stored procedure to implement the new formula function
* Use a migration to add the stored procedure

## Plugin Architecture

A Baserow plugin is fundamentally a folder named after the plugin, containing a
`backend` and/or a `web-frontend` folder. Baserow has two main services, a
Django `backend` API server and a Nuxt frontend
`web-frontend` server. A Baserow plugin can plug into either both or just one of these
services by populating the respective plugin sub-folder.

Since the `backend` service is built with Django, the `backend` sub-folder in a plugin
should be a Django [app](https://docs.djangoproject.com/en/3.2/ref/applications/).
Similarly, the `web-frontend` service is built using Nuxt.js, and so the `web-frontend`
plugin sub-folder should contain a Nuxt (
v2) [module](https://nuxtjs.org/tutorials/creating-a-nuxt-module/).

### Plugin Installation API

> The current Baserow Plugin API Version is `0.0.1-alpha`.

All the Baserow official images ship with the following bash scripts which are used to
install plugins. They can be used either in a Dockerfile at build time to bake a plugin
into a Docker image or to install a plugin into an existing Baserow container at
runtime.
`install_plugin.sh` can be used to install a plugin from an url, a git repo or a local
folder on the filesystem.

You can find these scripts in the following locations in our images:

1. `/baserow/plugins/install_plugin.sh`
2. `/baserow/plugins/uninstall_plugin.sh`
3. `/baserow/plugins/list_plugins.sh`

These scripts expect a Baserow plugin to follow the conventions described below.

### Plugin File Structure

The `install_plugin.sh/uninstall_plugin.sh` scripts expect your plugin to have a
specific structure as follows:

```
├── plugin_name
│  ├── baserow_plugin_info.json (A simple json file containing info about your plugin)
│  ├── backend/ (Your plugins django app which will be installed into the backend)
│  │  ├── setup.py
│  │  ├── build.sh (Called when installing the plugin in a Dockerfile/container)
│  │  ├── runtime_setup.sh (Called on first runtime startup of the plugin)
│  │  ├── uninstall.sh (Called when uninstalling the plugin in a container)
│  │  ├── src/plugin_name/src/config/settings/settings.py (Optional Django setting file)
│  ├── web-frontend/ (Your plugins nuxt module which will be installed into the web-frontend)
│  │  ├── package.json
│  │  ├── build.sh (Called when installing the plugin in a Dockerfile/container)
│  │  ├── runtime_setup.sh (Called on first runtime startup of the plugin)
│  │  ├── uninstall.sh (Called when uninstalling the plugin in a container)
│  │  ├── modules/plugin-name/module.js (Your plugins module file)
```

The backend and web-frontend sub folders come with three bash files which will be
automatically called by Baserow's plugin scripts during installation and uninstallation.
You can use these scripts to perform extra build steps, installation of packages, and
other docker container build steps required.

1. `build.sh`: Called when a plugin is built into a Dockerfile, or on container startup
   if a runtime installation is occurring.
2. `runtime_setup.sh`: Called when the first time a container starts up after the plugin
   has been installed, useful for running superuser commands on the embedded database if
   it exists.
3. `uninstall.sh` Called on uninstall, the database will be available and so any
   backwards migrations should be run here.

### The plugin info file

The `baserow_plugin_info.json` file is a json file, in your root plugin folder,
containing metadata about your plugin. It should have the following JSON structure:

```json
{
  "name": "TODO",
  "version": "TODO",
  "supported_baserow_versions": "2.0.6",
  "plugin_api_version": "0.0.1-alpha",
  "description": "TODO",
  "author": "TODO",
  "author_url": "TODO",
  "url": "TODO",
  "license": "TODO",
  "contact": "TODO"
}
```

### Expected plugin structure when installing --url or --git

When using `install_plugin.sh --url URL_TO_PLUGIN_TAR_GZ`
or `install_plugin.sh --git URL_TO_PLUGIN_REPO` the plugin archive/repo should contain a
single `plugins` folder, inside which there should a single plugin folder following the
structure above and has the same name as your plugin. By default,
the [plugin boilerplate](./boilerplate.md) generates a repository with this structure.
For example a conforming tar.gz archive should contain something like:

```
├─ * (an outermost wrapper directory named anything is allowed but not required) 
│  ├── plugins/ 
│  │  ├── plugin_name/
│  │  │  ├── baserow_plugin_info.json 
│  │  │  ├── backend/
│  │  │  ├── web-frontend/
```

## Writing a Plugin

Now you have created a plugin, lets go into more detail of how to actually extend and
customize Baserow using your plugin.

First you should read the following documentation for a basic introduction to Baserow's
technical architecture:

1. [Baserow Technical Introduction](../technical/introduction.md)
2. [Database Plugin](../technical/database-plugin.md)

### Storing State

If your plugin needs to store state, you should only ever do this in:

1. The database being used by Baserow
2. Using Django's default storage mechanism
3. The Redis being used by Baserow but only for non-persistent state like a cache that
   is fine to be destroyed at any moment.

**Never store any state in your plugin folder itself inside the container.** This folder
is deleted and recreated as part of the plugin installation process and any state you
store inside it can be lost.

### Writing a Backend Plugin

#### Adding Python Requirements

Your backend plugin is just a normal python module which will be installed into the
Baserow virtual environment using `pip` by `install_plugin.sh`. If using the plugin
boilerplate you can add any python requirements to the pip requirements file found
at `backend/requirements/base.txt`.

#### As a Django App

When the Baserow backend Django service starts up it looks for any plugins in the plugin
directory which have a `backend` sub-folder. If it finds any it assumes
the `backend/src/plugin_name/`
sub folder contains a Django App and adds it to the `INSTALLED_APPS`. This means that
your backend plugin must be a Django app whose name exactly matches the name of the
plugin folder.

In your plugin's Django app you can do anything that you normally can do with a Django
app such as having migrations, using the `ready()` method to do startup configuration
etc.

#### Backend Registries

Baserow has a number of registries which are used to dynamically configure Baserow. For
example the `field_type_registry` contains various implementations of the `FieldType`
class.

Each registry contains various implementations of a particular "interface" class. A
registry in Baserow is simply a singleton dictionary populated by apps in their `ready`
method. Then Baserow's various API endpoints will use these registries at runtime.

So in your plugin's Django Apps `ready` method is where you should import any relevant
registries and register your own implementations of field types.

For example, the `plugin_registry` is used to register implementations of the
`baserow.core.registries.Plugin` interface. You can create your own class which
implements this base class and register it with the `plugin_registry` by:

```python
from baserow.core.registries import plugin_registry
from django.apps import AppConfig


class PluginNameConfig(AppConfig):
    name = "my_baserow_plugin"

    def ready(self):
        from .plugins import PluginNamePlugin

        plugin_registry.register(PluginNamePlugin())
```

You can see all the different things you can dynamically register into Baserow with your
plugin by searching the Baserow codebase and inspecting the `registry.py` and
`registries.py` files.

### Writing a Web Frontend Plugin

#### Adding Node Requirements

Your web-frontend plugin is just a normal node package which will be installed into
Baserow's node_modules using `yarn` by `install_plugin.sh`. You can add any extra
frontend requires to your `web-frontend/package.json`.

#### Web-frontend Registries

The Baserow web-frontend nuxt app also follows the registry pattern that the backend
has. This means it has an equivalent frontend registry for most backend registries where
it makes sense. So if you were to registry a new field type in the backend registry then
also make sure to registry a new field type in the frontend registry also.

## Publishing your Plugin

The easiest way to share you plugin with others is by making a public git repository
using GitLab, GitHub or some other git host. Once you have pushed your plugin folder to
the git repository then anyone can then install your plugin following the steps in
the [Plugin Installation](./installation.md) guide.

Also, please share and post about your plugin on
our [Plugin community sub-forum](https://community.baserow.io/c/plugins/17)!

## Further Reading

Check out the following guides in the plugin section which go into more specifics on say
creating a new field type:

1. [Application Type Guide](./application-type.md)
1. [Field Type Guide](./field-type.md)
1. [Field Converter Guide](./field-converter.md)
1. [View Type Guide](./view-type.md)
1. [View Filter Type Guide](./view-filter-type.md)
