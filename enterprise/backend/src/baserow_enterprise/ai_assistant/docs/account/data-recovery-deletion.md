# Baserow Documentation

Source: https://baserow.io/user-docs/data-recovery-and-deletion

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Delete and recover data

When you erase data, it is temporarily stored in your account before it is permanently deleted. During this period, functions like the trash, undo/redo, recover, and the ability to check a history of who made what changes and when they were made, make it possible to restore accidentally deleted data.

  * How to [delete a workspace](/user-docs/delete-a-workspace). Note that you must be an admin of the workspace in order to delete it.
  * How to [delete a database](/user-docs/delete-a-database).
  * How to [delete a table](/user-docs/delete-a-table).
  * How to [delete a view](/user-docs/view-customization#delete-a-view).
  * How to [delete a field](/user-docs/field-customization#delete-field).

## Undo & redo functions

You can undo an action by clicking the undo/redo icon in the bottom-left corner to reverse a change (for example, if you deleted a row or changed a cell value).

Also, after your workspace, table, row or data has been removed for around seven seconds, a little popup with the word “Restore deleted” and an undo option will appear at the bottom of the screen. Your data will be recovered if you choose this undo option.

Use these shortcuts to alter the recent edits: `Cmd/Ctrl` \+ `Z` for Undo, `Cmd/Ctrl` \+ `Shift` \+ `Z` for Redo.

![Undo/Redo in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fd9bd0c2cbd5d68145edbd33aa54ee39080b252d.webp)

## Account trash

If you accidentally deleted an application or a workspace, don’t worry! Items are put in the trash for 3 days, and after that time, they are permanently erased. Your data will be automatically removed after this period of retention.

You can find out what was deleted, where it was deleted from when it was deleted, and who deleted it in each deletion entry.

Click **Trash** in the home screen sidebar under the Dashboard to access the trash. This will bring up a list of the deleted data from the past three days.

### Recover deleted data

A workspace or database that you delete will remain in your account trash for three days after being removed.

You can recover deleted database items including tables, fields, rows, and views using your account trash during that period.

To restore data from trash,

  1. In the sidebar, select **Trash**.
  2. In the **Trash** , navigate to the data you want to restore
  3. Click **Restore** next to a deleted item.

![Recover deleted data in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_13.49.23.png)

Admins can restore any deleted items. Members can restore items within a database or table.

### Empty trash

If you’d like to permanently delete your data before the three-day retention period, you can empty the trash. This will render any trash you delete unrecoverable.

When you no longer need the data, you can choose to empty the workspace or application trash. However, note that the action cannot be undone.

To permanently delete data from trash,

  1. In the sidebar, select **Trash**.
  2. In the **Trash** , navigate to the workspace or application you want to restore or empty
  3. Click **Delete workspace permanently** or **Empty this workspace’s trash**. Your workspace or application is deleted!

![Trash in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_13.55.20.png)

