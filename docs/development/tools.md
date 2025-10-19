# Development tools

## Backend

### PostgreSQL

Baserow uses PostgreSQL for persistent storage.

https://www.postgresql.org/

### Django

At the core of the backend we run the Django framework. A popular framework was chosen
to lower the barrier of creating a plugin. We also looked for a batteries included,
simple, and proven framework. Django was the obvious choice.

https://www.djangoproject.com

### Django REST framework

To quickly create endpoints, handle authentication, object serialization, validation,
and do many more things we use Django REST Framework. You will find it at the base or
every endpoint.

https://www.django-rest-framework.org/

### pytest

We use pytest to easily and automatically test all the python code. Most of the backend
code is covered with tests and we like to keep it that way! The code is also tested
in the [continuous integration pipeline](./code-quality.md). It can also be tested
manually in the development environment. Make sure that you are in the `backend`
container and execute the following command.

```
$ make test
```

https://docs.pytest.org/en/latest/contents.html

### Flake8

Flake8 makes it easy to enforce our python code style. The code is checked in the
continuous integration pipeline. It can also be checked manually in the development
environment. Make sure that you are in the `backend` container and execute the
following command. If all the code meets the standards you should not see any output.

```
$ make lint
```

https://flake8.pycqa.org/en/latest/

### Black

Black auto formats all of our python code into one opinionated consistent style. The
goal being to reduce and hopefully eliminate the need to worry about formatting whilst
writing and reviewing code.

https://black.readthedocs.io/en/stable/index.html

```
make format
```

### Internationalization

For internationalization (i18n), we leverage Django's built-in support. Django's internationalization framework allows us to easily translate our web application into multiple languages.

To use Django's internationalization features, we wrap our text with a special function called `gettext` or `gettext_lazy`.
For more information, refer to the [Django Internationalization and Localization documentation](https://docs.djangoproject.com/en/3.2/topics/i18n/).
Then, we created a Makefile command to collect or update all these strings into a message file.

```
make translations
```

This will call the Django's `makemessages` command for the English language of all the installed applications. The creation of the messages for the other languages and the step to compile all these messages, will be automatically handled by `Weblate` before each release.


### ItsDangerous

In order to safely share sensitive data like password reset tokens we use a proven
library called ItsDangerous.

https://itsdangerous.palletsprojects.com/en/1.1.x/

### DRF spectacular

Having up to date API documentation and having it in the OpenAPI specification format
is a must. To avoid mistakes, the contents are close to the code and are automated as
much as possible. DRF Spectacular offers all of this!

https://pypi.org/project/drf-spectacular/

### MJML

In order to simplify the process of creating HTML emails we use MJML. This tool makes
it easy to create responsive emails that work with most email clients. This might seem
a bit like over engineering to use this for only the password forgot email, but more
complicated emails are going to be added in the future and we wanted to have a solid
base.

https://mjml.io/

## Web frontend

### Vue.js

https://vuejs.org/

### Nuxt.js

Because of our experience with Vue.js and the great features Nuxt.js offers, the choice
of Nuxt as a frontend framework was obvious. It offers server side rendering, automated
code splitting, good project structure, modularity and lots of other features out of
the box. All of which are needed for Baserow.

https://nuxtjs.org/

### Stylelint

The tool Stylelint is used to make sure all the SCSS code is in the correct format. It
is used when the `make stylelint` is called and live in the development environment via
prettier.

https://stylelint.io/

### ESLint

ESLint is used to make sure all the JavaScript code is in the correct format. It is
used when the `make eslint` is called and it runs live in the development environment
via prettier.

https://eslint.org/

### Prettier

https://prettier.io/

### webpack

Bundles all the assets of Baserow. This is being used by default with Nuxt.js.

https://webpack.js.org/

### SCSS

https://sass-lang.com/

### JEST

Because of its simplicity and compatibility with Vue and Nuxt we have chosen to include
JEST as the framework for the web frontend tests. Almost no code is covered yet so we
can definitely improve on that. The code is also tested in the continuous integration
pipeline. It can also be tested manually in the development environment. Make sure
that you are in the `web-frontend` container and execute the following command.

```
$ make jest
```

https://jestjs.io/

### Iconoir

To improve the user experience we are using the Iconoir icons set in the web
frontend.

https://iconoir.com/

## Additional tools

### Changelog generator

The changelog generator is a custom-built tool we developed to make it easier for you to
write changelog entries which don't cause merge conflicts.

Every time a merge request is created and requires a changelog, the changelog generator
should be used to generate such changelog.

See [here](https://github.com/baserow/baserow/blob/master/changelog/README.md) for more details.

## Thanks!

Big thanks to creators and contributors of the tools described above! Without you
Baserow would not have been where it is today.
