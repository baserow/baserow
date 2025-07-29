# Baserow Documentation

Source: https://baserow.io/user-docs/personal-api-tokens

---


## Create a database token

A database token serves as a digital key, granting authorized users access to the database’s resources while ensuring data integrity and privacy.

To create a database token,

  1. Go to your profile, then navigate to the Settings page
  2. Click on the **Database Tokens** tab
  3. Click on the **Create token +** button
  4. Input the name and select an existing workspace
  5. Click on the **Create token** button to create a new database token for the selected workspace and for the authorized user.

![Create a Baserow database token](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a203fb56-598e-4340-bc27-50a32b08ec36/create%20token.webp)

To copy the token ID, select the ellipsis icon beside the selected workspace and copy the token.

> When the token sharing publicly, you must be cautious about setting the appropriate permissions. If you expose your token publicly, anyone with that token can create, read, update, and delete your data.

Learn more about updating API permissions.

### Generate a new database token

The user’s database access privileges are defined by the database token permissions. If you accidentally expose your database token to the public, we recommend that you generate a new one as soon as possible.

You can generate a new database token by clicking the ‘Generate new token’ button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9eb21e1b-3c79-4fde-8446-5e1333d2832b/Screenshot%202022-12-02%20at%2013.49.39.png)

### Delete a database token

You can delete an existing database token owned by an authorized user that has access to the related workspace.

Also, you can rename the token by clicking the **Rename** button.

## Database token permissions

Database tokens are effective if the token has the correct permissions. A database token can be used to create, read, update, and delete rows in a table. Include the access token in the API request to access data from the database.

It is possible to set permissions on the table level. The **Database table rows** endpoints can be used for these operations.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2b76157b-fd30-423d-90e4-fe120f48952c/Screenshot%202022-12-02%20at%2013.52.34.png)

The permission toggles indicate per operation which permissions the database token has within the whole workspace. If the value of for example `create` is `true`, then the token can create rows in all tables related to the workspace.

If all tables in the workspace are checked, then the token creates permissions for all the tables in the database selected. The same applies if a database reference is provided.

## Related content

  * [Baserow webhooks](/user-docs/webhooks).
  * [Baserow authentication and token types](/blog/authenticate-baserow-using-database-json-web-token).
  * [Database API documentation](/user-docs/database-api).
  * [Database and table IDs](/user-docs/database-and-table-id).
  * [Backend API](/docs/apis%2Frest-api).

