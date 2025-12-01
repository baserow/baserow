# Baserow's Cloudron image 

This is the Baserow maintained [Cloudron Image](https://cloudron.io).

Please see our [Install on Cloudron](https://baserow.io/docs/installation/install-on-cloudron)
guide for more details.

## About Baserow

* A spreadsheet database hybrid combining ease of use and powerful data organization.
* Easily self-hosted with no storage restrictions or sign-up on https://baserow.io to
  get started immediately.
* Alternative to Airtable.
* Open-core with all non-premium and non-enterprise features under
  the [MIT License](https://choosealicense.com/licenses/mit/) allowing commercial and
  private use.
* Headless and API first.
* Uses popular frameworks and tools like [Django](https://www.djangoproject.com/),
  [Vue.js](https://vuejs.org/) and [PostgreSQL](https://www.postgresql.org/).

## Quick Reference

* **Maintained By**: [baserow.io](https://baserow.io/contact)
* **Get Support At**: [The Baserow Community Forums](https://community.baserow.io)
* **Source Code Available At**: [github.com/baserow/baserow](https://github.com/baserow/baserow)
* **Docs At**: [baserow.io/docs](https://baserow.io/docs)
* **License**: Open-Core with all non-premium and non-enterprise code under the MIT 
  license.

## Supported tags and Dockerfile Links

* [`X.Y.Z`](https://github.com/baserow/baserow/blob/master/deploy/cloudron/Dockerfile)
  Tagged by Baserow version.
* [`latest`](https://github.com/baserow/baserow/blob/master/deploy/cloudron/Dockerfile)
* [`develop-latest`](https://gitlab.com/baserow/baserow/-/blob/develop/deploy/cloudron/Dockerfile)
  This is a bleeding edge image from our development branch, use at your own risk.

## Application builder domains

Baserow has an application builder that allows to deploy an application to a specific
domain. Because Cloudron has a reverse proxy that routes a domain to the right Cloudron
app, the deployed application isn't automatically available on the chosen domain.

To make this work, you must add a domain alias in the Cloudron settings. This can be
done by going to the settings of your Baserow app, then click on `Location`, click on
`Add an alias`, and then add the domain you've published the application to in Baserow.
Make sure that the alias matches the full domain name in Baserow. After that, Cloudron
will request the SSL certificate, and then you can visit your domain.

It's also possible to add a wildcard alias to Cloudron, but the SSL certificate then
doesn't work out of the box. Some additional settings on Cloudron might be required to
make it work.
