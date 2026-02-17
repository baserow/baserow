# Field Metadata System

## Overview

The field metadata system provides a way to store and manage per-field, per-row metadata in Baserow tables. This metadata is stored separately from the actual field values and is used to track additional information about fields that doesn't belong in the primary data model.

**Example use case**: Tracking AI field generation status (generating, success, error) with timestamps and error details.

## Architecture

### Storage Layer

#### Database Schema

Metadata is stored in a JSONB column named `field_metadata` on each table. New tables automatically include this column. 
For existing tables, the column is added when first needed by a field type that uses metadata.

The column is automatically included in the table model when `field_metadata_column_added=True`. 
A GIN index is automatically created on the column for efficient JSONB containment and existence queries.

**Internal storage format** (in database):
```json
{
  "456": {  // field_id as string - GENERATING state
    "start": 1762348609.808954   // generation started (Unix timestamp)
  },
  "457": {  // ERROR state (start is replaced on completion)
    "end": 1762348612.789012,
    "ok": false,
    "error": "API timeout"        // error message (only when ok=false)
  },
  "458": {  // SUCCESS state (not returned in API, start is replaced)
    "end": 1762348625.789012,
    "ok": true
  }
}
```

**API format** (transformed for frontend):
```json
{
  "456": {"status": "generating"},  // has start, no end
  "457": {"status": "error"}        // has end, ok=false
  // 458 not included - success state is not returned
}
```

Status is derived from the internal format:
- Has `start` but no `end` → `"generating"`
- Has `end` with `ok=true` → not returned (success = absence of metadata)
- Has `end` with `ok=false` → `"error"`

**Key design decisions**:
- Field IDs are stored as strings (JSON requirement)
- Default empty object `{}` avoids NULL handling
- Status derived from timestamps/flags, not stored directly
- The `field_metadata` column is automatically included for all tables:

### Core Components

#### 1. FieldMetadataHandler

**Location**: `backend/src/baserow/contrib/database/fields/metadata_handler.py`

Generic handler providing CRUD operations for field metadata. See the source file for method signatures.

**Key features**:
- Uses PostgreSQL's `jsonb_set` with `COALESCE` for atomic updates, avoiding race conditions
- Custom Django ORM `Func` class (`JSONBRemoveKey`) for JSONB `-` operator to remove keys atomically
- All methods gracefully degrade when metadata column doesn't exist


#### 2. Field-Specific Handlers

Field types can implement handlers with domain-specific logic.

**Example: AIFieldMetadataHandler**

**Location**: `premium/backend/src/baserow_premium/fields/ai_field_metadata.py`

Provides AI-specific methods for managing generation status:
- Set rows to "generating" state (clears any previous state)
- Combined helper that sets status AND broadcasts WebSocket update
- Mark as successful with completion timestamp
- Mark as failed with error details
- Clear metadata for rows (when batch fails midway)
- Broadcast metadata updates via WebSocket

See the source file for method signatures and implementation details.

### API Integration

#### Row Metadata Registry

**Location**: `backend/src/baserow/contrib/database/rows/registries.py`

The `row_metadata_registry` provides a plugin system for exposing metadata via the API.

**Implementation example**: `premium/backend/src/baserow_premium/fields/row_metadata_types.py`

The `AIFieldMetadataType` class:
1. Extends `RowMetadataType` base class
2. Fetches metadata from database for specified rows
3. Transforms internal format to API format
4. Provides API documentation via serializer field
5. Is registered in the `row_metadata_registry`


#### API Usage

Metadata is opt-in via the `?include=row_metadata` query parameter:

**Grid view request**:
```
GET /api/database/views/grid/123/?include=row_metadata
```

**Response**:
```json
{
  "count": 10,
  "results": [
    {
      "id": 456,
      "field_789": "Generated text value"
    }
  ],
  "row_metadata": {
    "456": {
      "ai_field": {
        "789": {"status": "generating"}
      },
      "row_comment_count": 3
    }
  }
}
```

**AI field metadata format**:
- `{"status": "generating"}` - AI is currently generating a value
- `{"status": "error"}` - Generation failed
- No metadata returned for success state (absence = success or never generated)

**Supported endpoints**:
- Grid view: `GET /api/database/views/grid/{view_id}/`
- Gallery view: `GET /api/database/views/gallery/{view_id}/`
- Kanban view: `GET /api/database/views/kanban/{view_id}/` (premium)
- Calendar view: `GET /api/database/views/calendar/{view_id}/` (premium)
- Timeline view: `GET /api/database/views/timeline/{view_id}/` (premium)

All use `@allowed_includes("field_options", "row_metadata")` decorator.

### Real-time Updates

#### Websocket Messages

The system provides real-time metadata updates via websockets.

**New signal**: `rows_metadata_updated` in `backend/src/baserow/contrib/database/rows/signals.py`

**Implementation**: `backend/src/baserow/contrib/database/ws/rows/signals.py`

The signal handler:
1. Listens for `rows_metadata_updated` signal
2. Fetches latest metadata from database via `row_metadata_registry`
3. Broadcasts `rows_metadata_updated` websocket message with metadata
4. Uses `transaction.on_commit()` to ensure consistency
5. Use broadcast helper `AIFieldMetadataHandler.broadcast_generation_started()` to broadcast the metadata update to connected clients


#### Websocket Message Flow

**Scenario: AI field generation**

1. **User triggers generation** (API call)
   ```
   POST /api/database/fields/789/generate-ai-values/
   ```
   - Returns `HTTP 202 ACCEPTED`
   - Celery task enqueued

2. **Task starts, metadata updated to "generating"**
   ```python
   AIFieldMetadataHandler.set_generating_and_broadcast(
       ai_field, row_ids, user
   )
   ```

   **Websocket broadcast**:
   ```json
   {
     "type": "rows_metadata_updated",
     "table_id": 100,
     "row_ids": [456],
     "metadata": {
       "456": {
         "ai_field": {
           "789": {"status": "generating"}
         }
       }
     }
   }
   ```

3. **AI generates value**

4. **Task completes successfully**
   ```python
   with transaction.atomic():
       AIFieldMetadataHandler.set_success(model, row.id, field.id)
       RowHandler().update_row_by_id(...)  # Triggers rows_updated signal
   ```

   **Websocket broadcast** (via existing `rows_updated` signal):
   ```json
   {
     "type": "rows_updated",
     "table_id": 100,
     "rows": [{"id": 456, "field_789": "Generated text..."}],
     "metadata": {},
     "updated_field_ids": [789]
   }
   ```

   Note: Success state returns empty metadata for the AI field (absence = success).

5. **On error**
   ```python
   AIFieldMetadataHandler.set_error(model, row.id, field.id, str(exc))
   rows_metadata_updated.send(...)
   ```

   **Websocket broadcast**:
   ```json
   {
     "type": "rows_metadata_updated",
     "table_id": 100,
     "row_ids": [456],
     "metadata": {
       "456": {
         "ai_field": {
           "789": {"status": "error"}
         }
       }
     }
   }
   ```

   Note: Error details (message, type) are stored internally but not exposed in the API.


## Design Patterns

### 1. Graceful Degradation

Always check if metadata is available before using:

```python
if FieldMetadataHandler.is_metadata_available(model):
    AIFieldMetadataHandler.set_generating(ai_field, row.id)
```

### 2. Readable Keys with Constants

Use constants for keys to enable refactoring while keeping storage readable:

```python
class MyMetadataKeys:
    START = "start"        # When operation started
    END = "end"            # When operation completed
    OK = "ok"              # True=success, False=error
    ERROR = "error"        # Error message (only when ok=False)

metadata = {
    MyMetadataKeys.START: timezone.now().timestamp(),
}

{"start": 1762348609.808954}
```


### 3. Atomic Transactions for Consistency

When updating both row values and metadata, use a transaction:

```python
with transaction.atomic():
    # Update metadata first
    FieldMetadataHandler.set_metadata(...)

    # Then update row (this triggers signals)
    RowHandler().update_row_by_id(...)

```

### 4. Preserve Existing Metadata

When updating status, preserve timestamps:

```python
FieldMetadataHandler.set_metadata(
    model,
    [MetadataUpdate(
        row_id=row_id,
        field_id=field_id,
        metadata={
            MyMetadataKeys.STATUS: "completed",
            MyMetadataKeys.FINISHED_AT: timezone.now().timestamp(),
        }
    )],
    merge=True  # Uses jsonb_set for atomic merge
)
```

### 5. Cleanup on Field Operations

Metadata is automatically cleaned up when fields are deleted or modified. The `FieldHandler` calls lifecycle hooks on `FieldMetadataHandler` during field deletion and type changes, ensuring no orphaned metadata remains.

## Performance Considerations

### Database Queries

- **GIN indexes** on JSONB columns enable fast queries
- **Atomic updates** via `jsonb_set` avoid race conditions
- **Bulk operations** available for multi-row updates

### API Performance

- **Opt-in metadata**: Only loaded when `?include=row_metadata` is specified
- **Registry pattern**: Multiple metadata types can coexist efficiently
- **Single query**: All metadata types fetched in one pass

### Websocket Performance

- **Deferred broadcasting**: Uses `transaction.on_commit()` to ensure data consistency
- **Targeted updates**: Only affected rows notified
- **Lightweight messages**: Metadata-only updates skip row value serialization
