# Backend API

Baserow is divided into two components, the **backend** and the 
**web-frontend**, which talk to each other via a REST API. This page
contains some documentation about those endpoints and how to use them. These endpoints
should never be used to show data on your own website because that would mean you have
to expose your credentials or JWT token. They should only be used the make changes in
your data. You can publicly expose your data in a safe way by creating a
[database token](https://api.baserow.io/api/redoc/#operation/create_database_token)
token, set the permissions and follow the automatically generated api docs at
https://baserow.io/api-docs.

In the future there are going to be features that enable you to expose 
your data publicly in a safe way.

## OpenAPI spec

There is a full specification of the API available here 
https://api.baserow.io/api/redoc/. You will find documentation and some examples for 
each endpoint. The OpenAPI spec can also be downloaded in JSON format here 
https://api.baserow.io/api/schema.json.

## Authentication

In order to use most of the endpoints you need an authorization token and in order to 
get one you need an account. Below you will find a small example on how to create an 
account.

```
POST /api/user/
Host: api.baserow.io
Content-Type: application/json

{
  "name": "Bram",
  "email": "bram@localhost.com",
  "password": "your_password"
}
```
or
```
curl -X POST -H 'Content-Type: application/json' -i https://api.baserow.io/api/user/ --data '{
  "name": "Bram",
  "email": "bram@localhost.com",
  "password": "your_password"
}'
```

The server should respond with a `200` status code which means your account has been 
created. The provided email address will be your username. More information about this 
endpoint can be found in the API spec at 
https://api.baserow.io/api/redoc/#operation/create_user.

Now that you have created an account, you need a JWT token to authorize each following
request. This can be requested using the following example.

```
POST /api/user/token-auth/
Host: api.baserow.io
Content-Type: application/json

{
  "username": "bram@localhost.com",
  "password": "your_password"
}
```
or
```
curl -X POST -H 'Content-Type: application/json' -i https://api.baserow.io/api/user/token-auth/ --data '{
  "username": "bram@localhost.com",
  "password": "your_password"
}'
```

If you inspect the JSON response you will notice a key named 'token'. The value is the 
token that you need for all the other requests. More information about this endpoint
can be found in the API spec at https://api.baserow.io/api/redoc/#operation/token_auth.
You can simply provide an `Authorization` header containing `JWT {TOKEN}` to authorize. 
The token will be valid for 60 minutes and can be refreshed before that time using the
https://api.baserow.io/api/redoc/#operation/token_refresh endpoint.

The following example will list all the workspaces that belong to your account. When you 
just have created an account an example workspace has been created automatically. More 
information about this endpoint can be found in the API spec at 
https://api.baserow.io/api/redoc/#operation/list_workspaces.

```
GET /api/workspaces/
Host: api.baserow.io
Content-Type: application/json
Authorization: JWT {YOUR_TOKEN}
```
or
```
curl -X GET -H 'Content-Type: application/json' -H 'Authorization: JWT {YOUR_TOKEN}' -i 'https://api.baserow.io/api/workspaces/'
```

## Common issues

### 415 Unsupported Media Type

If you ever get the error "Unsupported media type", you most likely need to add the 
following HTTP header to your request. This is so that the server knows your body is in 
JSON format.

```
Content-Type: application/json
```

## Row authors and collaborators

Created-by, last-modified-by and multiple-collaborators values identify retained
Subjects. Responses contain `{ "id": 123, "name": "Alex", "type": "auth.User" }`
or `{ "id": 456, "name": "Assistant", "type": "core.Agent" }`. UID and email are
not exposed by these values. Existing human IDs stay equal to their User IDs;
Agent Subject IDs are independent of Agent API IDs.

Collaborator requests continue accepting lists such as `[{ "id": 456 }]`.
Only eligible identities from the table's workspace can be selected. Assignment
never grants workspace or table access. Removed and deleted identities remain
visible in existing values. Human-only mentions still use User IDs.

Agent field references require the `agents` feature flag and the persisted
[Subject rollout gate](../technical/subject-rollout.md).
