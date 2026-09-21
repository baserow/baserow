# WebSocket API

The web socket API is used for real time collaboration. When a user makes a change, for
example when creating a new database application, then the backend broadcasts a message
containing that application to all the users within the related workspace and who are
connected to the web socket. The web-frontend uses the web socket to update already
fetched data in real time when it has changed. This ensures that the user is always
working with the most recent data without reloading the page.

## Connecting

In order to connect to the web socket you first need to authenticate via the REST API
and obtain a [JSON Web Token](https://jwt.io/). After that you can connect to the
following URL providing your JWT as query parameter: 
`wss://api.baserow.io/ws/core/?jwt_token=YOUR_JWT_TOKEN`. If you self host
you need to replace `api.baserow.io` with your own backend URL. The web socket
connection only receives messages targeted at the workspaces that the authenticated user
belongs to. Below is an example of how to connect to the web socket in JavaScript.

```javascript
const socket = new WebSocket('wss://api.baserow.io/ws/core/?jwt_token=YOUR_JWT_TOKEN')
socket.onopen = () => {
    console.log('The connection is made')
}
socket.onmessage = (message) => {
    console.log('Received', message)
}
```

## Messages

Broadcasted messages containing real time updates are always JSON, and they
always contain a key named `type` which indicates what has changed. For example
`create_application` could be the value of the type and in this case an additional key
`application` is provided containing the newly created application in serialized form.

Below you will find an example of a message when another user has created a database
application in a workspace that the receiver also belongs to. There are of course many event
types, they are described at the bottom of this page.

```json
{
   "type": "application_created",
   "application": {
      "id": 123,
      "name": "Test",
      "order": 8,
      "type": "database",
      "workspace": {
         "id": 1,
         "name": "Bram's workspace"
      },
      "tables": []
   }
}
```

## Web Socket ID

After making the connection you will receive an `authentication` message indicating if
the JWT token authentication was successful. If so, the message will also contain a
`web_socket_id`. When making a change via the API, for example creating a new
application, you can provide that id as header `WebSocketId: {YOUR_WEB_SOCKET_ID}` to
exclude yourself from the message containing the change that has already been executed.
Below you will find such an example authentication message including `web_socket_id`
and an example HTTP request containing the `WebSocketId` header.

```json
{
  "type": "authentication",
  "success": true,
  "web_socket_id": "934254ab-0c87-4dbc-9d71-7eeab029296c"
}
```

```
PATCH /api/applications/1/
Host: api.baserow.io
Content-Type: application/json
WebSocketId: 934254ab-0c87-4dbc-9d71-7eeab029296c

{
  "name": "Test",
}
```

## Subscribe to a page

A user will receive all the core messages related to workspaces and application by default,
but we also have messages related to certain pages, for example to the table page.
Because we don't want to cause an overload of messages you can subscribe to a page of your interest. It is also possible to be subscribed to multiple pages. If
successful you will receive messages related to that page. You will need to manually unsubscribe from a page to stop receiving updates.

### Table page

Subscribing to a table page will request updates related to a Baserow table that will
give you information about new rows, row updates, and other relevant information. 

A table page expects the`table_id` parameter. Below you will find an example how to subscribe to that page.

```json
{
  "page": "table",
  "table_id": 1
}
```

Once successfully subscribed you will receive a confirmation message indicating that you
are subscribed to the page.

```json
{
    "type": "page_add",
    "page": "table",
    "parameters": {
        "table_id": 1
    }
}
```

### Row page

Subscribing to a Row page will request additional updates related to a Baserow row of a particular table that will give you information like row history updates. Please note that to get updates such as row deletions and similar, you should use the table page described above.

A Row page expects the`table_id` and `row_id` parameters. Below you will find an example how to subscribe to that page.

```json
{
  "page": "row",
  "table_id": 1,
  "row_id": 1
}
```

Once successfully subscribed you will receive a confirmation message indicating that you
are subscribed to the page.

```json
{
    "type": "page_add",
    "page": "row",
    "parameters": {
        "table_id": 1,
        "row_id": 1
    }
}
```

## Unsubscribing from a page

To stop receiving updates related to a page you are subscribed to, you will need to send a `remove_page` message with the same page parameters that led to the subscription:

```json
{
  "remove_page": "row",
  "table_id": 1,
  "row_id": 1
}
```

## Messages types

* `authentication`
* `page_add`
* `page_discard`
* `before_group_deleted`
* `user_updated`
* `user_deleted`
* `user_restored`
* `user_permanently_deleted`
* `group_created`
* `group_updated`
* `group_deleted`
* `group_restored`
* `group_user_added`
* `group_user_updated`
* `group_user_deleted`
* `application_created`
* `application_updated`
* `application_deleted`
* `applications_reordered`

### Database message types

* `table_created`
* `table_updated`
* `table_deleted`
* `tables_re_ordered`
* `field_created`
* `field_updated`
* `field_deleted`
* `field_restored`
* `button_fields_updated`
* `rows_created`
* `rows_updated`
* `rows_deleted`
* `before_rows_update`
* `before_rows_delete`
* `row_history_updated`
* `view_created`
* `view_updated`
* `view_deleted`
* `view_filter_created`
* `view_filter_updated`
* `view_filter_deleted`
* `view_filter_group_created`
* `view_filter_group_updated`
* `view_filter_group_deleted`
* `view_sort_created`
* `view_sort_updated`
* `view_sort_deleted`
* `view_decoration_created`
* `view_decoration_updated`
* `view_decoration_deleted`
* `view_field_options_updated`
* `views_reordered`

### Premium message types

* `row_comment_created`
* `row_comment_updated`
* `row_comment_deleted`
