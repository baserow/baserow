# Testing Builder authentication with Keycloak

The Docker development environment includes an optional Keycloak service with a
preconfigured OpenID Connect client, SAML client, and test user. Enable it by adding
the `authentication` Compose profile to `.env.docker-dev` or `.env.local`:

```bash
COMPOSE_PROFILES=...,authentication
```

Start the development environment normally with `just dc-dev up`. Keycloak is then
available at:

* `http://keycloak:8080` from other Docker Compose services.
* `http://localhost:8081` from the host and browser.

Set `BASEROW_KEYCLOAK_PORT` in `.env.docker-dev` to change the host port. This is
needed when running multiple development environments at the same time. The Keycloak
administrator credentials are `admin` / `admin`.

The imported clients use `PUBLIC_BACKEND_URL` for their OIDC callbacks and SAML ACS.
Recreate the Keycloak container after changing this URL because realm imports only
create missing realms.

The imported `baserow-dev` realm has one test user:

* Username: `builder-user`
* Password: `builder-user`
* Email: `builder-user@example.com`

These fixed credentials are intended for local development only.

## OpenID Connect

Add an OpenID Connect authentication provider to a Builder user source with:

* Name: `Keycloak development`
* Base URL from Docker: `http://keycloak:8080/realms/baserow-dev`
* Base URL from a natively running backend (you need to add a domain to your hosts file as localhost is not a valid url): `http://<anydomain>:8081/realms/baserow-dev`
* Client ID: `baserow-builder`
* Secret: `baserow-builder-secret`

Use `email`, `given_name`, and `family_name` for the email, first-name, and last-name
claim keys respectively. Keycloak advertises the localhost authorization endpoint to
the browser while dynamically advertising its Compose hostname for backend requests.

If `BASEROW_KEYCLOAK_PORT` is changed, replace `8081` in the native backend URL above.

## SAML

Download the realm metadata from:

```text
http://localhost:8081/realms/baserow-dev/protocol/saml/descriptor
```

Add a SAML authentication provider to a Builder user source and paste the downloaded
XML into the metadata field. Configure it with:

* Domain: `example.com`
* Email attribute: `user.email`
* First-name attribute: `user.first_name`
* Last-name attribute: `user.last_name`

The imported SAML client uses the Builder ACS under `PUBLIC_BACKEND_URL`. Delete and
recreate the Keycloak container if that URL or `BASEROW_KEYCLOAK_PORT` changes after
the initial import.

The realm is not persisted, so recreating the Keycloak container restores the fixture
to its committed state.
