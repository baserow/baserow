# Baserow Documentation

Source: https://baserow.io/user-docs/database-api

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Database API documentation

In this section, we will learn how to connect Baserow with other software.

Baserow makes authentication easy and secure for seamless integration with third-party applications. We are API-first which means it can be integrated with every tool you need to build apps, automate processes and drive productivity.

## Overview

[REST APIs](/api-docs) are core operational tools that enable organizations and developers to consume and build on top of Baserow’s various database capabilities. Baserow API follows REST semantics, uses JSON to encode objects, and relies on standard HTTP codes, and machine and human-readable errors to signal operation outcomes.

The rules and functions to follow in order to make an API call are laid out in the database documentation. Understanding this will help us efficiently manage data retrieval and manipulations through the API.

Baserow API consists of different endpoints for specific actions:

  * List fields `GET` `/api/database/fields/table/{table_id}/`
  * List rows `GET` `/api/database/rows/table/{table_id}/`
  * Get row `GET` `/api/database/rows/table/{table_id}/{row_id}/`
  * Create row `POST` `/api/database/rows/table/{table_id}/`
  * Update row `PATCH` `/api/database/rows/table/{table_id}/{row_id}/`
  * Move row `PATCH` `/api/database/rows/table/{table_id}/{row_id}/move/`
  * Delete row `DELETE` `/api/database/rows/table/{table_id}/{row_id}/`
  * List all tables `GET` `/api/database/tables/`

![connect Baserow with other software](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d715b098-52e7-4824-8206-ccee20986652/Screenshot%25202022-07-01%2520at%252015.35.55.png)

## View API docs

After you have created your database schema and API key in the settings, your Baserow database provides its own REST API endpoints to create, read, update, and delete rows. The [database documentation](/api-docs) is generated automatically based on the tables and fields that are in your database.

To access the database API documentation,

  1. Click on the vertical ellipsis `⋮` beside the selected database.
  2. Select **View API Docs** from the menu.

![Database API documentation](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5741a747-4a97-4ea1-b207-4e11480d63fb/Database%20API%20documentation.png)

If you make changes to your database, table, or fields it could be that the API interface has also changed. Therefore, ensure that you update your API implementation accordingly.

> You can create and update rows with [link row](/user-docs/link-to-table-field), [single select](/user-docs/single-select-field), and [multiple select](/user-docs/multiple-select-field) values by providing the values of the target rows’ [primary field](/user-docs/primary-field) e.g. `["name of row 1", "name of row 2", "name of row 3", "name of row 4"]` or by providing the internal numerical IDs e.g. `[1,2,3,4]`.

## Token-based authentication

In order to use most of the endpoints you need an authorization token and in order to get one you need an account.

Baserow uses a simple token-based authentication. You need to [generate at least one database token](/user-docs/personal-api-tokens) in your settings to use the endpoints. It is possible to give create, read, update, and delete permissions up until table level per token.

Authenticate to the API by providing your [database token](/user-docs/personal-api-tokens) in the HTTP authorization bearer token header. All API requests must be authenticated and made over HTTPS.

## Error handling

The API uses standard HTTP status codes to indicate the success or failure of requests. Note that as of the recent updates:

  * **HTTP 409 Conflict** : Returned when a request fails due to a deadlock (previously returned HTTP 503)
  * **HTTP 503 Service Unavailable** : No longer used for deadlock errors

This change provides more accurate error reporting and helps distinguish between temporary service issues and conflict-based failures.

## OpenAPI spec

There is a full specification of the API available here <https://api.baserow.io/api/redoc/>. You will find documentation and some examples for each endpoint. The OpenAPI spec can also be downloaded in JSON format here <https://api.baserow.io/api/schema.json>.

View our [OpenAPI specification](https://api.baserow.io/api/redoc/).

## Related content

  * [Baserow webhooks](/user-docs/webhooks).
  * [Generate database tokens](/user-docs/personal-api-tokens).
  * [Database and table IDs](/user-docs/database-and-table-id).
  * [Backend API.](/docs/apis%2Frest-api)

