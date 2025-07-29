# Baserow Documentation

Source: https://baserow.io/user-docs/created-by-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Created by field

When a [new row is created](/user-docs/how-to-make-new-rows), Baserow automatically populates the “Created by” field with the name of the active collaborator. The information remains unchanged even if the row is edited or modified by others.

## Overview

The Created by field in Baserow automatically tracks and displays the name of the collaborator who created each row within a table.

It facilitates accountability and collaboration by making it clear who originated the information and helps in tracing back decisions and actions to specific individuals for historical reference or follow-up.

The Created by field is a non-editable field that displays [collaborator’s name](/user-docs/managing-workspace-collaborators), ensuring data integrity and preventing unauthorized changes. It can be used in formulas to trigger actions based on row creators.

![Created by field in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/95398426-eb1f-480c-b9ff-6d0ec3165106/Created%20by.png)

## Add a Created by field

  1. Open your Baserow database and the desired table.
  2. Click the `+` button to add a new field.
  3. Search for **Created by** and select it.
  4. Click **Create**.

When a new row is created, Baserow automatically populates the “Created by” field with the name of the active collaborator. The information remains unchanged even if the record is edited or modified by others.

The Created by field does not track edits or updates made by other collaborators after creation. For more comprehensive activity tracking, consider using the [Last modified by field](/user-docs/last-modified-by-field).

## Related content

  * [Field overview](/user-docs/baserow-field-overview)
  * [Create a field](/user-docs/adding-a-field)
  * [Field configuration options](/user-docs/field-customization)
  * [Collaboration overview](/user-docs/managing-workspace-collaborators)
  * [Add workspace collaborators](/user-docs/working-with-collaborators)
  * [Manage workspace members](/user-docs/manage-workspace-permissions)

