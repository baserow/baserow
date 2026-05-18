# Files and user uploads

How user-uploaded files (file fields, profile pictures, exports,
imports, AI assets) are stored, deduplicated, served, and migrated.

The system lives in `backend/src/baserow/core/user_files/` and is
backed by `django-storages` — local disk, S3, Azure Blob, or Google
Cloud Storage are the supported backends. The choice is one env var;
the code is backend-agnostic.

For the ops side (configuring storage, secure file serve) see
[Secure file serve](../installation/secure-file-serve.md) and
[Configuration](../installation/configuration.md).

## The `UserFile` model

`backend/src/baserow/core/user_files/models.py`:

| Column | Purpose |
|---|---|
| `original_name` | The user's filename at upload time. Shown in the UI. |
| `original_extension` | The extension (used in the storage name). |
| `unique` | 32-char random suffix to disambiguate identical-hash uploads. |
| `sha256_hash` | Content hash — drives deduplication. |
| `size`, `mime_type`, `is_image`, `image_width`, `image_height` | Metadata cached at upload. |
| `uploaded_by`, `uploaded_at` | Audit. |
| `deleted_at` | Marker set by explicit cleanup paths after storage deletion. |

The **storage filename** is deterministic:

```python
@property
def name(self):
    return f"{self.unique}_{self.sha256_hash}.{self.original_extension}"
```

A `UserFile` row is reused when the same original filename and content hash
already exist and have not been soft-deleted. Otherwise the upload gets a new
`unique` value and therefore a new storage name. The file is immutable once
created.

> The `name` carries both `unique` and `sha256_hash` so any file path
> stored anywhere in the system can be validated against its content
> without an extra DB lookup. `UserFile.deconstruct_name(name)` parses
> a name back into `{unique, sha256_hash, original_extension}`.

`UserFile` is **append-only conceptually**. The serializer comment is
explicit: *"the state of the UserFile never changes."* Don't mutate
rows after creation — re-upload and reference the new one.

## `UserFileHandler` — the entry point

`backend/src/baserow/core/user_files/handler.py`. All file work
goes through this handler. The main operations:

- **`upload_user_file(user, file_name, stream, storage=None)`** —
  given a readable stream, computes the sha256, stores under
  `{unique}_{hash}.{ext}`, creates the `UserFile` row, returns it.
  If the file is an image, generates configured thumbnails inline.
- **`upload_user_file_by_url(user, url, file_name=None, storage=None)`** —
  fetches a remote URL and uploads it. Used by template installs,
  Airtable imports, AI-generated images.
- **`get_user_file_url(user_file)`** — returns the storage URL for
  a file. May be a signed URL depending on the storage backend and
  secure-file-serve setting.
- **`get_user_file_by_name(...)`** — fetch a `UserFile` from its
  storage name. Used when validating references in serializers.
- **`export_user_file(...)` / `import_user_file(...)`** — embed the
  file's bytes in a snapshot/template ZIP and re-instantiate it on
  import. See [Serialization](serialization-system.md).

## Storage backend

Configured via the standard Django `STORAGES` setting in
`backend/src/baserow/config/settings/base.py`. The `default` storage
is what `UserFileHandler` uses unless an explicit `storage=` is
passed. In production this is typically S3 / Azure / GCS;
in development it's local disk.

Switching backends is an env-var operation — there are no
backend-specific code paths in the handler. `django-storages`
abstracts away the differences (multipart uploads, signed URLs,
existence checks). If your code needs to do something the
abstraction can't express, that's a sign to talk through alternatives
in review rather than reach for an SDK-specific feature.

## Content-type safety — active content neutralisation

A file labeled `image.jpg` could be SVG with embedded JavaScript. Or
HTML masquerading as an image. Or an executable. Baserow's
`UserFileHandler` runs every upload through
`_resolve_mime_type_and_active_content(...)` and
`_neutralize_active_content(...)`:

- The real MIME type is detected from the bytes, not the filename or
  the client's `Content-Type` header.
- "Active content" types (HTML, SVG with scripts, JavaScript) are
  served with `Content-Disposition: attachment` and a sanitised
  content-type so the browser downloads them instead of executing.
- Extensions that would let the user navigate to executable content
  are mangled before storage.

This is **the** reason `UserFileHandler.upload_user_file` is the
only way to land bytes in user-file storage. Don't write directly
to the storage backend — you bypass the safety pass.

## Thumbnails

`USER_THUMBNAILS` setting:

```python
USER_THUMBNAILS = {
    "tiny": [None, 21],       # height-only
    "small": [48, 48],
    "card_cover": [300, 160],
}
```

`generate_and_save_image_thumbnails(...)` runs at upload for image
files and saves a sized variant per entry under
`{USER_THUMBNAILS_DIRECTORY}/{thumbnail_name}/{original_name}`. The
frontend reads the appropriate variant based on context — list views
use `tiny`, grid cells use `small`, gallery cards use `card_cover`.

Adding a new thumbnail size:

1. Add the entry to `USER_THUMBNAILS`.
2. Run a backfill management command — historical files won't have
   the new size until they're re-thumbnailed.
3. The frontend can request the new size via the same naming pattern.

The thumbnail pipeline is synchronous (it runs inside
`upload_user_file`). For huge files this would block the request;
the file-size limit (`BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB`) keeps it
bounded. Don't add a "generate thumbnails async" path without
talking through invalidation — the row's `is_image` and
`image_width/height` columns are written at the same time and the
frontend assumes thumbnails are ready when the upload returns.

## Secure file serve

By default, files are served via direct storage URLs (S3 signed
URLs, or the `MEDIA_URL` static path). With
`BASEROW_SERVE_FILES_THROUGH_BACKEND=true`, files are served through
Baserow's own endpoint which enforces an additional permission
check before returning the bytes.

The trade-off:

- **Direct URLs** are faster (one request to storage, no Baserow
  round-trip). Anyone with the URL can fetch it for as long as it's
  valid.
- **Secure file serve** runs every fetch through Django, so revoking
  access is immediate. Costs the round-trip on every file load.

Use secure file serve when files contain customer data with
permission-sensitive content (Enterprise installs typically do).
For purely public assets (gallery view cover images on a public
view), direct URLs are fine.

See [Secure file serve](../installation/secure-file-serve.md) for
the ops setup.

## Where files appear in Baserow

| Surface | Owner | Notes |
|---|---|---|
| `file` field on a user table | Field type → `FileFieldType` | Stored as a list of `UserFile.name` references in a JSON column. The field type knows how to serialize/deserialize this against `UserFile` rows. |
| Profile pictures | `User.profile_image` | One `UserFile` per user. |
| Workspace logo | `Workspace` settings | One `UserFile` per workspace. |
| Exports | `ExportJob` outputs | The job writes to a `UserFile`; the URL is returned to the user. |
| Imports | `FileImportJob` input | The user uploads a `UserFile`; the job parses it. |
| Builder app assets | Element types | Same `UserFile` machinery, just attached to builder element rows. |
| AI-generated content | `ai` field type, assistant tools | The model output is fetched as a URL and saved through `upload_user_file_by_url`. |

All of these go through `UserFileHandler`. Anywhere a Baserow row
holds a "file" reference, it's a `UserFile.name` string — never a
raw storage path or URL.

## Lifecycle — when files are deleted

Files are **not** deleted when the row referencing them is deleted, and
`UserFile` rows are not reference-counted. A row, view, builder element, job,
or snapshot stores a `UserFile.name`; deleting that parent object does not
automatically remove the file from storage.

The reasons:

- A row deletion in Baserow is also a trash event (see
  [Trash system](trash-system.md)). If the user restores the row
  within the retention window, the file reference needs to still
  resolve.
- Snapshots and templates can re-import files; eager deletion would
  break the re-import.

The `deleted_at` column is used when a cleanup path explicitly removes a file
from storage, for example the `delete_files_uploaded_by_user` management
command. Upload deduplication ignores rows with `deleted_at` set so a new
upload won't reuse a storage object that has already been removed.

If you need to add a new file reference, **don't** wire a
`post_delete` signal to remove the file. The trash cleanup pass
does not own user-file cleanup; design an explicit cleanup path if the feature
needs one.

## Tests

Use the `data_fixture.create_user_file(...)` helper. Tests don't need
to hit the storage backend — the test settings use an in-memory
storage. For tests that need real file behaviour (thumbnail
generation, content-type detection), set
`MEDIA_ROOT` to a tempdir.

## Anti-patterns

- **Writing directly to the storage backend.** Bypasses
  `UserFileHandler.upload_user_file` and skips the safety pass.
  Always go through the handler.
- **Storing arbitrary paths as "file references".** The `UserFile.name`
  is the only valid reference shape. It carries the sha256 so
  anything else can be validated against the bytes; an arbitrary
  path can't.
- **Mutating a `UserFile` row in place.** Re-upload and reference the
  new one. The row is conceptually append-only.
- **Long-running file processing in the upload request.** Thumbnails
  are bounded; anything else (OCR, content extraction, ML inference)
  belongs in a Job.
- **Building URLs by string-concatenating storage paths.** Use
  `UserFileHandler.get_user_file_url(user_file)`. It honours secure
  file serve and the backend's URL conventions.
- **Forgetting to register the file reference in `export_serialized`.**
  Templates and snapshots will reference a missing file on import.

## Adding a new feature that uses files

The recipe:

1. **Decide where the reference lives.** A model column? A JSON blob?
   Whatever it is, the value is `UserFile.name`.
2. **Hand uploads to `UserFileHandler.upload_user_file(...)`** —
   never write to storage directly.
3. **Resolve URLs via `UserFileHandler.get_user_file_url(user_file)`**
   — never construct them yourself.
4. **Wire serialization**: implement `export_user_file` /
   `import_user_file` (or call the handler's wrappers) so snapshots,
   templates, and duplications carry the file.
5. **Test** with `data_fixture.create_user_file(...)`. Verify the
   reference survives a round-trip through export/import.

## Related

- [Serialization system](serialization-system.md) — how
  `export_user_file` / `import_user_file` interact with snapshots
  and templates.
- [Trash system](trash-system.md) — file lifecycle vs row trash.
- [Jobs](jobs.md) — imports / exports run as jobs and read/write
  files.
- [Secure file serve](../installation/secure-file-serve.md) — ops
  setup.
- [Configuration](../installation/configuration.md) — storage env
  vars (`STORAGES`, `BASEROW_SERVE_FILES_THROUGH_BACKEND`,
  `BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB`, …).
- [AI field architecture](../development/ai-field-architecture.md)
  — uses `upload_user_file_by_url` to fetch generated content.
