# Installation on Render

> Any questions, problems or suggestions with this guide? Ask a question in our
> [community](https://community.baserow.io/) or contribute the change yourself at
> https://github.com/baserow/baserow/tree/develop/docs .

[Render](https://render.com) is a modern alternative to Heroku, a platform as a service.
Render enables you to build, run and operate applications entirely in the cloud. We have
created a template that allows you to easily install Baserow on the "Standard" paid
plan and the paid Postgres plan provided by Render.

## The template

> Currently, we only support running Baserow on the $25 per month "Standard" Render
> plan additionally with their $7 per month Postgres plan for performance reasons.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/baserow/baserow/tree/master)
The button above can be used to install Baserow on [Render](https://render.com) with one
click. You may need to manually enter the `https://github.com/baserow/baserow/`
repository URL and choose the branch
`master`.

After installation, you can reach Baserow on the URL provided by Render.

## Built-in Baserow templates disabled by default

In our template because we are only using 1 Baserow worker the initial template sync
will block other background tasks, such as exporting tables. As a result we have by
default disabled the loading of our built-in example templates. You can trigger this
manually by:

1. Login Render and go to your Baserow web-service 
2. Click the "Shell" sidebar link
3. Enter and run the following command `./baserow.sh backend-cmd manage sync_templates`

Every time you upgrade your Render Baserow app you will need to repeat the steps above
the get the latest Baserow templates.

## Persistent S3 file storage

By default, the uploaded files are stored inside the Render service for demo purposes.
This means that everytime your render service restarts, you will lose all your uploaded
files. Your files can optionally be stored inside an S3 bucket. To do so, you need to
add a couple of config vars to the settings. Go to your Baserow web-service in Render
and click on the "Environment" section. Here you need to add the following vars:

* AWS_ACCESS_KEY_ID: The access key for your AWS account.
* AWS_SECRET_ACCESS_KEY: The secret key for your AWS account.
* AWS_STORAGE_BUCKET_NAME: Your Amazon Web Services storage bucket name.
* AWS_S3_REGION_NAME *Optional*: Name of the AWS S3 region to use (eg. eu-west-1)
* AWS_S3_ENDPOINT_URL *Optional*: Custom S3 URL to use when connecting to S3, including
  scheme.
* AWS_S3_CUSTOM_DOMAIN *Optional*: Your custom domain where the files can be downloaded
  from.

### Non AWS S3 providers

It is also possible to use non AWS, S3 providers like for example Digital Ocean. Below
you will find example settings if you want to connect to Digital Ocean Spaces.

* AWS_ACCESS_KEY_ID: The spaces API key.
* AWS_SECRET_ACCESS_KEY: The spaces API secret key.
* AWS_STORAGE_BUCKET_NAME: The name of your space.
* AWS_S3_REGION_NAME: Name of the Digital Ocean spaces region (eg. ams3)
* AWS_S3_ENDPOINT_URL: (eg. https://ams3.digitaloceanspaces.com)
* AWS_S3_CUSTOM_DOMAIN: (eg. name-of-your-space.ams3.digitaloceanspaces.com)

### Workers per service

To spare resources, every Baserow service in Render has only one worker by default. If
you are upgrading to a more powerful Render plan, you can increase the amount of workers
to 2. This can be done via the Environment section on your Baserow web-service in
Render. Find the "BASEROW_AMOUNT_OF_WORKERS" var and set the value to your desired
number of workers.

You can roughly estimate the amount of workers based on the available RAM of your
service type. Every worker needs around 512MB ram.

## Updating to the latest version of Baserow

When a new version of Baserow has been released, you probably want to update. To do so
on your render Baserow web-service you can click the "Manual Deploy" button and select "
Deploy latest commit".
