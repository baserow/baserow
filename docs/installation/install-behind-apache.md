# Installing Baserow behind Apache

If you have an [Apache server](https://www.apache.com/) this guide will explain how to
configure it to pass requests through to Baserow.

We strongly recommend you use our `baserow/baserow:2.0.6` image or the example
`docker-compose.yml` files (excluding the `.no-caddy.yml` variant) provided in
our [git repository](https://github.com/baserow/baserow/tree/master/deploy/apache/).

These come with a pre-configured, simple and lightweight Caddy http server which 
simplifies your life by:

1. Routing requests to the correct internal Baserow services
2. Enabling websocket connections for realtime collaboration
3. Serving user uploaded files
4. **And it still runs behind your own reverse proxy with no problems**

> If you do not want to use our embedded Caddy service behind your Apache then
> make sure you are using one of the two following deployment methods: 
>
> * Your own container setup with our single service `baserow/backend:2.0.6`
    and `baserow/web-frontend:2.0.6` images.
> * Or our `docker-compose.no-caddy.yml` example file in our [git repository](https://github.com/baserow/baserow/tree/master/deploy/apache/).
> 
> Then you should use **Option 2: Without our embedded Caddy** section instead.

## Option 1: With our embedded Caddy

> You can find a Dockerized working example of using Apache with Baserow in our git repo in
> the [deploy/apache/recommended](https://github.com/baserow/baserow/tree/master/deploy/apache/)
> folder.

Follow this option if you are using:

* The all-in-one Baserow image `baserow/baserow:2.0.6`
* Any of the example compose files found in the root of our git
  repository `docker-compose.yml`/`docker-compose.local-build.yml`
  /`docker-compose.all-in-one.yml`

### Prerequisites

We assume you already have an Apache server running which you know how to configure. If
not please first follow guides such
as [this one](https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod_proxy-extension-ubuntu-20-04#step-1-enabling-necessary-apache-modules)
to get familiar with Apache.

Additionally, we assume you are using a debian based operating system and have already
successfully deployed Baserow. 

### Step 1 - Enable the required Apache modules

The Apache config shown later needs the following modules enabled.

```bash
# First enable the required Apache modules and restart
sudo a2enmod proxy headers proxy_http proxy_wstunnel rewrite 
sudo systemctl restart apache2
```

### Step 2 - Configure Baserow's BASEROW_PUBLIC_URL

Baserow needs to know the URL it will be accessed on. We'll assume you will be hosting
Baserow on a subdomain and so you should set the following environment variable on your
Baserow deployment (see [Configuring Baserow](./configuration.md) for more details).

```
BASEROW_PUBLIC_URL=http://baserow.example.com
```

### Step 3 - Add apache config for Baserow

Create a new file in your `/etc/apache2/sites-enabled/baserow-site.conf` using the
example below:

> Make sure to replace any http://localhost:PORT references with the correct ones for
> your particular Baserow deployment.

```
<VirtualHost *:80>
ProxyPreserveHost On

# Replace with your sub domain
ServerName example.localhost

# Properly upgrade ws connections made by Baserow to the /ws path for realtime collab.
RewriteEngine on
RewriteCond ${HTTP:Upgrade} websocket [NC]
RewriteCond ${HTTP:Connection} upgrade [NC]
RewriteRule .* "ws://localhost:8080/$1" [P,L,END]
ProxyPass /ws ws://localhost:8080/ws
ProxyPassReverse /ws ws://localhost:8080/ws

# Send everything else to Baserow as normal.
ProxyPass / http://localhost:8080/
ProxyPassReverse / http://localhost:8080/

</VirtualHost>
```

### Step 4 - Enable the new Baserow site

Finally, you should enable your new Baserow site and restart your Baserow server if you
made environment variable changes.

```bash
sudo a2ensite baserow-site.conf
```

You should now be able to access Baserow on you configured subdomain.

## Option 2: Without our embedded Caddy

> You can find a Dockerized working example of using Apache with Baserow in our git repo in
> the [deploy/apache/no-caddy](https://github.com/baserow/baserow/tree/master/deploy/apache/)
> folder.

Follow this option if you are using:

* Our standalone `baserow/backend:2.0.6` and `baserow/web-frontend:2.0.6` images with
  your own container orchestrator.
* Or the `docker-compose.no-caddy.yml` example docker compose file in the root of our
  git repository.

### Prerequisites

We assume you already have an Apache server running which you know how to configure. If
not please first follow guides such
as [this one](https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod_proxy-extension-ubuntu-20-04#step-1-enabling-necessary-apache-modules)
to get familiar with Apache.

Additionally, we assume you are using a debian based operating system and have already
successfully deployed Baserow. If you are using a different setup the 
general steps and Apache config should still be a useful starting point for you,
but you might have to run different commands.

### Step 1 - Enable the required Apache modules

The Apache config shown later needs the following modules enabled.

```bash
# First enable the required Apache modules and restart
sudo a2enmod proxy headers proxy_http proxy_wstunnel rewrite 
sudo systemctl restart apache2
```

### Step 2 - Mount the media volume so Apache can serve uploaded files

You need to ensure user uploaded files are accessible in a folder for Apache to serve. In
the rest of the guide we will use the example `/var/web` folder for this purpose.

If you are using the `baserow/backend:2.0.6` image then you can do this by adding
`-v /var/web:/baserow/data/media` to your normal `docker run` command used to launch the
Baserow backend.

If you are instead using the `docker-compose.no-caddy.yml` then you can change all of
the
`- media:/baserow/media` mounts to be `- /var/web:/baserow/media`.

### Step 3 - Configure Baserow's BASEROW_PUBLIC_URL

Baserow needs to know the URL it will be accessed on. We'll assume you will be hosting
Baserow on a subdomain and so you should set the following environment variable on your
Baserow deployment (see [Configuring Baserow](./configuration.md) for more details).

```
BASEROW_PUBLIC_URL=http://baserow.example.com
```

### Step 4 - Create your new baserow-site.conf

Create a new file in your `/etc/apache2/sites-enabled/baserow-site.conf` using the
example below:

> Make sure to replace any http://localhost:PORT references with the correct ones for
> your particular Baserow deployment.

```
<VirtualHost *:80>
ProxyPreserveHost On

# Replace with your sub domain
ServerName example.localhost

# Serve user uploaded files and add the Content-Disposition header when the filename
# query param is set.
RewriteCond %{QUERY_STRING} (?:^|&)dl=([^&]+)
RewriteRule ^/media/.* - [E=FILENAME:%1]
Header set "Content-Disposition" "attachment; filename=\"%{FILENAME}e\"" env=FILENAME
ProxyPass /media !
Alias /media /var/www
<Directory "/var/www/">
    Require all granted
</Directory>


# Properly upgrade ws connections made by Baserow to the /ws path for realtime collab.
RewriteEngine on
RewriteCond ${HTTP:Upgrade} websocket [NC]
RewriteCond ${HTTP:Connection} upgrade [NC]
RewriteRule .* "ws://localhost:8000/$1" [P,L,END]
ProxyPass /ws ws://localhost:8000/ws
ProxyPassReverse /ws ws://localhost:8000/ws

ProxyPass /api http://localhost:8000/api
ProxyPassReverse /api http://localhost:8000/api

ProxyPass / http://localhost:3000/
ProxyPassReverse / http://localhost:3000/

</VirtualHost>
```

### Step 5 - Enable the new Baserow site

Finally, you should enable your new Baserow site and restart your Baserow server if you
made environment variable changes.

```bash
sudo a2ensite baserow-site.conf
```

You should now be able to access Baserow on you configured subdomain.

### Troubleshooting

If you can upload images to Baserow but no thumbnails show, or you can't re-download
them (you are getting 403 denied errors when accessing the files) then:

* Make sure the permissions on the sub-folders in /var/web are set to be readable by
  your Apache user by running `cd /var/web && chmod 755 *`.
* Fix any file permissions found inside the `/var/web` sub-folders to be readable by
  your Apache user.

