# Plugin Installation

> Check out our [Plugin community sub-forum](https://community.baserow.io/c/plugins/17)
> for community made plugins and further discussion.

Before we begin, Baserow plugins are in **early preview** and so there are important
things to know:

* A Baserow plugin when installed has full access to your data and can execute any code
  it likes. Baserow does not sandbox, isolate or perform any security checks on plugins.
* Baserow does not yet verify or guarantee the safety of any plugins and does not take
  responsibility for any damage or loss caused by installing or using any plugins.
* Using Baserow plugins is entirely at your own risk, make sure you trust the source and
  make backups before using any plugin.
* They are only recommended for use by advanced users who are comfortable with Docker,
  volumes, containers and the command line.
* There are a number of missing plugin features, e.g. there is no UI for inspecting
  installed plugins and everything is done via the command line.

## Plugin Installation

There are a few ways to install a plugin:

### By building your own all-in-one image

The easiest, fastest and most reliable way to install a Baserow plugin currently is to
build your own image based off the Baserow all-in-one image.

1. It is highly recommended that you backup your data before installing a plugin, see
   the [Docker install guide backup section](../installation/install-with-docker.md)
   for more details on how to do this.
2. Ensure you have [docker](https://docs.docker.com/engine/install/) installed, and it
   is upto date.
3. Now create a new file called `Dockerfile`. We will use this file to build a custom
   Baserow image with your desired plugins installed.
4. Next copy the contents shown into your `Dockerfile`

```dockerfile
FROM baserow/baserow:2.0.6

# You can install a plugin found in a git repo:
RUN /baserow/plugins/install_plugin.sh \
    --git https://github.com/example/example_baserow_plugin.git
    
# Or you can download a tar.gz directly from an url 
RUN /baserow/plugins/install_plugin.sh \
    --url https://example.com/plugin.tar.gz
    
# Or you can install the plugin from a local folder by copying it into the image and \
# then installing using --folder
COPY ./some_local_dir_containing_your_plugin/ /baserow/data/plugins/your_plugin/
RUN /baserow/plugins/install_plugin.sh \
    --folder /baserow/data/plugins/your_plugin/

# The --hash flag below will make the install_plugin.sh script check that the 
# plugin exactly matches the provided hash. 
#
# We recommend you provide this flag to make sure the downloaded plugin has not
# been maliciously modified. 
#
# To get the hash of a plugin simply run the docker build with a nonsense --hash
# value. Then the build will fail and `install_plugin.sh` will print the hash of the 
# downloaded plugin. Then you can replace your nonsense --hash value with the printed
# one and build again.
RUN /baserow/plugins/install_plugin.sh \
    --git https://github.com/example/example_baserow_plugin.git \
    --hash hash_of_plugin_2
```

5. Choose which of the `RUN` commands you'd like to use to install your plugins and
   delete the rest, replace the example URLs with ones pointing to your plugin.
6. Now build your custom Baserow with the plugin installed by running:
   `docker build -t my-customized-baserow:2.0.6 .`
7. Finally, you can run your new customized image just like the normal Baserow image:
   `docker run -p 80:80 -v baserow_data:/baserow/data my-customized-baserow:2.0.6`

### Installing in an existing Baserow all-in-one container

This method installs the plugin into an existing container, and it's data volume.

1. It is highly recommended that you backup your data before installing a plugin, see
   the [Docker install guide backup section](../installation/install-with-docker.md)
   for more details on how to do this.
2. Now run the following command to install a plugin into your stopped container (
   replace the example URL and optional hash with your desired plugin):

```bash
docker exec baserow \
  ./baserow.sh install-plugin \
  --git https://github.com/example/example_baserow_plugin.git \
  --hash hash_of_plugin_1
```

3. Finally, restart your Baserow server to enable the plugin by
   running `docker restart baserow`.

### Using an environment variable

You can use the `BASEROW_PLUGIN_GIT_REPOS` or `BASEROW_PLUGIN_URLS` env variables when
using the Baserow images to install plugins on startup.

1. The `BASEROW_PLUGIN_GIT_REPOS` should be a comma separated list of https git repo
   urls which will be used to download and install plugins on startup.
2. The `BASEROW_PLUGIN_URLS` should be a comma separated list of urls which will be used
   to download and install .tar.gz files containing Baserow plugins on startup.

For example, you could start a new Baserow container with plugins installed by running:

```bash
docker run \
  -v baserow_data:/baserow/data \ 
  # ...  All your normal launch args go here
  -e BASEROW_PLUGIN_GIT_REPOS=https://example.com/example/plugin1.git,https://example.com/example/plugin2.git
  baserow:2.0.6
```

These variables will only trigger and installation when found on startup of the
container. To uninstall a plugin you must still manually follow the instructions below.

### Caveats when installing into an existing container

If you ever delete the container you've installed plugins into at runtime and re-create
it, the new container is created from the `baserow/baserow:2.0.6` image which does not
have any plugins installed.

However, when a plugin is installed at runtime or build time it is stored in the
`/baserow/data/plugins` container folder which should be mounted inside a docker volume.
On startup if a plugin is found in this directory which has not yet been installed into
the current container it will be re-installed.

As long as you re-use the same data volume, you should not lose any plugin data even if
you remove and re-create the containers. The only effect is on initial container startup
you might see the plugins re-installing themselves if you re-created the container from
scratch.

### Installing into standalone Baserow service images

Baserow also provides `baserow/backend:2.0.6` and `baserow/web-frontend:2.0.6` images
which only run the respective backend/celery/web-frontend services. These images are
used for more advanced self-hosted deployments like a multi-service docker-compose, k8s
etc.

These images also offer the `install-plugin`/`uninstall-plugin`/`list-plugins` CLI when
used with docker run and a specified command and the plugin env vars shown above, for
example:

```
docker run --rm baserow/backend:2.0.6 install-plugin ... 
docker run -e BASEROW_PLUGIN_GIT_REPOS=https://example.com/example/plugin1.git,https://example.com/example/plugin2.git --rm baserow/backend:2.0.6
```

You can use these scripts exactly as you would in the sections above to install a plugin
in a Dockerfile or at runtime. The scripts will automatically detect if they are running
in a `backend` only or `web-frontend` only image and only install the respective
plugin `backend` or `web-frontend` module.

The [plugin boilerplate](./boilerplate.md) provides examples of doing this in the
`backend.Dockerfile` and `web-frontend.Dockerfile` images.

## Uninstalling a plugin

**WARNING:** This will remove the plugin from your Baserow installation and delete all
associated data permanently.

### Uninstalling when using a custom Dockerfile

1. It is highly recommended that you backup your data before uninstalling a plugin, see
   the
   [Docker install guide backup section](../installation/install-with-docker.md)
   for more details on how to do this.
2. Stop your Baserow server first - `docker stop baserow`
3. `docker run --rm -v baserow_data:/baserow/data baserow:2.0.6 uninstall-plugin plugin_name`
4. Now the plugin has uninstalled itself and all associated data has been removed.
5. Edit your custom `Dockerfile` and remove the plugin.
6. Rebuild your image - `docker build -t my-customized-baserow:2.0.6 .`
7. Remove the old container using the old image - `docker rm baserow`
8. Run your new image with the plugin removed
    - `docker run -p 80:80 -v baserow_data:/baserow/data my-customized-baserow:2.0.6`
9. If you fail to do this if you ever recreate the container, your custom image still
   has the plugin installed and the new container will start up again with the plugin
   re-installed.

### Uninstalling a plugin installed directly into a container

1. It is highly recommended that you backup your data before uninstalling a plugin, see
   the
   [Docker install guide backup section](../installation/install-with-docker.md)
   for more details on how to do this.
2. To uninstall a plugin not installed using a Dockerfile but instead directly installed
   into an existing container you should run the following command whilst the container
   is running (assuming it is called `baserow`):
3. `docker exec baserow ./baserow.sh uninstall-plugin plugin_name`
4. Now the plugin has uninstalled itself and all associated data has been removed.
5. Finally, restart your Baserow by running `docker restart baserow`.

### Uninstalling a plugin installed using an environment variable

1. It is highly recommended that you backup your data before uninstalling a plugin, see
   the
   [Docker install guide backup section](../installation/install-with-docker.md)
   for more details on how to do this.
2. To uninstall a plugin you installed using one of `BASEROW_PLUGIN_GIT_REPOS`
   or `BASEROW_PLUGIN_URLS`
   you need to make sure that you delete and recreate the container with the plugin
   removed from the corresponding environment variable. If you fail to do so and just
   `uninstall-plugin` using exec and restart, the plugin will be re-installed after the
   restart as the environment variable will still contain the old plugin. To do this you
   must:
    1. `docker stop baserow`
    2. `docker run --rm -v baserow_data:/baserow/data baserow:2.0.6 uninstall-plugin plugin_name`
    3. Now the plugin has uninstalled itself and all associated data has been removed.
    4. Finally, recreate your Baserow container by using the same `docker run` command
       you launched it with, just make sure the plugin you uninstalled has been removed
       from the environment variable.

## Checking which plugins are already installed

Use the `list-plugins` command or built in `/baserow/plugins/list_plugins.sh` script to
check what plugins are currently installed.

```bash
docker run \
  --rm \
  -v baserow_data:/baserow/data \ 
  baserow:2.0.6 list-plugins 

# or on a running container

docker exec baserow /baserow/plugins/list_plugin.sh
```
