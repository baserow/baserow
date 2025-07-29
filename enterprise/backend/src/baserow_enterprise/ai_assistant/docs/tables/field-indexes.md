# Baserow Documentation

Source: https://baserow.io/user-docs/field-indexes

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
## Field indexes

![Field indexes](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2ef7dfc3-0962-4049-b11d-37aabba395b6/Field%20indexes.png)

Field indexes improve performance across your databases by speeding up filter operations, especially in large tables.

By creating indexes on frequently queried fields, Baserow can execute filters and API queries significantly faster. This optimization can reduce query times by up to 80%, making your workflows smoother and more efficient when dealing with large datasets.

### How to add a field index

  1. Go to the table and select the field you frequently use in filters or API requests.
  2. Click on **Edit field**.
  3. In the field editor, go to the **Advanced** tab.
  4. Toggle the **Index** option.

Once indexing is enabled, Baserow will automatically maintain the index in the background, ensuring queries remain fast without any additional effort from you.

> **Note** : Not all field types support indexing. If the option is unavailable, it may not be supported for that specific type.

