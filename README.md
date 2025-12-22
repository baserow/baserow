## Baserow: build databases, automations, apps & agents with AI — no code

Baserow is the secure, open-source platform for building databases, applications,
automations, and AI agents — all without code. Trusted by over 150,000 users, Baserow
delivers enterprise-grade security with GDPR, HIPAA, and SOC 2 Type II compliance, plus
cloud and self-hosted deployments for full data control. With a built-in AI Assistant
that lets you create databases and workflows using natural language, Baserow empowers
teams to structure data, automate processes, build internal tools, and create custom
dashboards. Fully extensible and API-first, Baserow integrates seamlessly with your
existing tools and performs at any scale.

* A spreadsheet database hybrid combining ease of use and powerful data organization.
* Create applications and portals, and publish them on your own domain.
* Automate repetitive workflows with automations.
* Visualize your data with dashboards.
* Kuma, powerful AI-assistant to builds complete solutions.
* GDPR, HIPAA, and SOC 2 Type II compliant.
* Easily self-hosted with no storage restrictions or sign-up on https://baserow.io to
  get started immediately.
* Best Alternative to Airtable.
* Open-core with all non-premium and non-enterprise features under
  the [MIT License](https://choosealicense.com/licenses/mit/) allowing commercial and
  private use.
* Headless and API first.
* Uses popular frameworks and tools like [Django](https://www.djangoproject.com/),
  [Vue.js](https://vuejs.org/) and [PostgreSQL](https://www.postgresql.org/).

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy/?template=https://github.com/baserow/baserow/tree/master)

```bash
docker run -v baserow_data:/baserow/data -p 80:80 -p 443:443 baserow/baserow:2.0.6
```

![Baserow database screenshot](docs/assets/screenshot.png "Baserow database screenshot")

![Baserow form screenshot](docs/assets/screenshot_kuma_form.png "Baserow form view and Kuma screenshot")

![Baserow kanban screenshot](docs/assets/screenshot_kanban.png "Baserow kanban view screenshot")

![Baserow application builder](docs/assets/screenshot_application_builder.png "Baserow application builder screenshot")

![Baserow application builder](docs/assets/screenshot_automations.png "Baserow automations screenshot")

![Baserow application builder](docs/assets/screenshot_dashboard.png "Baserow dashboard screenshot")

## 🚨 Repository Migration Notice

Baserow has moved from GitLab to GitHub. All issues have been successfully migrated,
but merged and closed merge requests (PRs) were not imported. You can still browse the
old repository and its history at: https://gitlab.com/baserow/baserow.

Please use this GitHub repository  for all new issues, discussions, and contributions
going forward at: https://github.com/baserow/baserow.

## Get Involved

Join our forum at https://community.baserow.io/. See
[CONTRIBUTING.md](./CONTRIBUTING.md) on how to become a contributor.

## Installation

* [**Docker**](docs/installation/install-with-docker.md)
* [**Helm**](docs/installation/install-with-helm.md)
* [**Docker Compose** ](docs/installation/install-with-docker-compose.md)
* [**Heroku**: Easily install and scale up Baserow on Heroku.](docs/installation/install-on-heroku.md)
* [**Render**: Easily install and scale up Baserow on Render.](docs/installation/install-on-render.md)
* [**Digital Ocean**: Easily install and scale up Baserow on Digital Ocean.](docs/installation/install-on-digital-ocean.md)
* [**AWS**: Install in a scalable way on AWS](docs/installation/install-on-aws.md)
* [**Cloudron**: Install and update Baserow on your own Cloudron server.](docs/installation/install-on-cloudron.md)
* [**Railway**: Install Baserow via Railway.](docs/installation/install-on-railway.md)
* [**Elestio**: Fully managed by Elestio.](https://elest.io/open-source/baserow)

## Official documentation

The official documentation can be found on the website at https://baserow.io/docs/index
or [here](./docs/index.md) inside the repository. The API docs can be found here at
https://api.baserow.io/api/redoc/ or if you are looking for the OpenAPI schema here
https://api.baserow.io/api/schema.json.

## Development environment

If you want to contribute to Baserow you can setup a development environment like so:

```
$ git clone https://github.com/baserow/baserow.git
$ cd baserow
$ ./dev.sh --build
```

The Baserow development environment is now running.
Visit [http://localhost:3000](http://localhost:3000) in your browser to see a working
version in development mode with hot code reloading and other dev features enabled.

More detailed instructions and more information about the development environment can be
found
at [https://baserow.io/docs/development/development-environment](./docs/development/development-environment.md)
.

## Why Baserow?

Unlike proprietary tools like Airtable, Baserow gives you **full data ownership**,
**infinite scalability**, and **no vendor lock-in** — all while keeping the simplicity
of a spreadsheet interface.

## Plugin development

Because of the modular architecture of Baserow it is possible to create plugins. Make
your own fields, views, applications, pages, or endpoints. We also have a plugin
boilerplate to get you started right away. More information can be found in the
[plugin introduction](./docs/plugins/introduction.md) and in the
[plugin boilerplate docs](./docs/plugins/boilerplate.md).

## Meta

Created by Baserow B.V. - bram@baserow.io.

Distributes under the MIT license. See `LICENSE` for more information.

Version: 2.0.6

The official repository can be found at https://github.com/baserow/baserow.

The changelog can be found [here](./changelog.md).

Become a GitHub Sponsor [here](https://github.com/sponsors/bram2w).
