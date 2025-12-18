# Installation on Cloudron

> Any questions, problems or suggestions with this guide? Ask a question in our
> [community](https://community.baserow.io/) or contribute the change yourself at
> https://github.com/baserow/baserow/tree/develop/docs .

Cloudron is a complete solution for running apps on your server and keeping them
up-to-date and secure. If you don't have Cloudron installed on a server you can follow
the [installation instructions here ](https://docs.cloudron.io/installation/). Ensure
you follow the installation guide to the end and log into the cloudron app store. Once
you have Cloudron installed and running on your service you can follow the steps below
to install the Baserow app.

## Install 

When Cloudron is installed and running, you can install Baserow by following these steps:
1. Open the Cloudron app store by navigating to your Cloudron URL in a web browser
2. Search for "Baserow" in the app store
3. Click on the Baserow app and then click on the "Install" button
4. Follow the prompts to configure the Baserow app domain
5. Once the installation is complete, you can access Baserow by navigating to the
   domain you specified during the installation process or just click on the Baserow app in
   the Cloudron dashboard

## Updates

Cloudron automatically handles updates for all installed apps, including Baserow. When
a new version of Baserow is released, Cloudron will automatically update the app to the latest
version without any manual intervention required.

## Extra settings

### Application builder domains

Baserow has an application builder that allows to deploy an application to a specific
domain. Because Cloudron has a reverse proxy that routes a domain to the right Cloudron
app, the deployed application isn't automatically available on the chosen domain.

To make this work, you must add a domain alias in the Cloudron settings. This can be
done by going to the settings of your Baserow app, then click on `Location`, click on
`Add an alias`, and then add the domain you've published the application to in  Baserow.
Make sure that the alias matches the full domain name in Baserow. After that, Cloudron
will request the SSL certificate, and then you can visit your domain.

It's also possible to add a wildcard alias to Cloudron, but the SSL certificate then
doesn't work out of the box. Some additional settings on Cloudron might be required to
make it work.
