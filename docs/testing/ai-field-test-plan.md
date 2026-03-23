# AI Field Test Plan

## Prerequisites

### 1. Instance-level configuration (env vars)

Configure at least one AI provider using the env vars documented in the
[Generative AI configuration](../installation/configuration.md#generative-ai-configuration)
section of `configuration.md`.

Verify: after setting env vars and restarting, the configured providers and models
appear in the AI field creation form.

### 2. Workspace-level configuration

1. Go to workspace **Settings → AI models**
2. Add an API key and select models for at least one provider
3. Verify: the workspace-level models appear in the AI field form for that
   workspace
4. Verify: workspace keys override instance keys — if instance has provider X
   configured and workspace also sets provider X with different models, only the
   workspace models appear
5. Verify: a provider configured only at instance level (no workspace override)
   still appears and works

### 3. Licensing

The AI field requires a **Premium** license. Verify:

- Without Premium: AI field type is not available in the field creation dropdown
- Without Premium: the generate button shows a Premium upgrade modal
- With Premium: field creation and generation work normally
- If a user who enabled auto-update loses Premium, auto-update stops for their
  fields

## Field creation

### 4. Basic creation

1. Create a table with a **Name** (text) column and a few rows
2. Add an AI field — the form should show:
   - AI provider + model selector (only configured providers)
   - Temperature input
   - File field selector (only if the selected provider supports files)
   - Output type selector (Text / Choice)
   - Auto-update checkbox
   - Prompt input (formula-enabled, can reference other fields)
3. Set provider, model, and prompt (e.g. `Summarize: {Name}`)
4. Save → field is created, cells are empty

### 5. Output types

**Text output:**
- Create an AI field with output type **Text**
- Generate values → cells contain free-form text

**Choice output:**
- Create an AI field with output type **Choice**
- Configure select options (e.g. Positive, Negative, Neutral)
- Generate values → each cell contains one of the defined options
- Verify: the AI response is fuzzy-matched to the closest option (e.g. model
  returns "positive" → maps to "Positive")

### 6. File field support

1. Create a **File** field and upload a mix of images (.png, .jpg) and documents
   (.pdf, .csv, .docx)
2. Create an AI field using **OpenAI** as the provider
3. Verify: the file field selector is visible and lists file fields
4. Select the file field and set a prompt (e.g. `Describe the contents of the file`)
5. Generate → the model processes the file content
6. Switch the provider to **Anthropic** or **Mistral** → verify the file field
   selector disappears (these providers don't support files)
7. Verify: saving an AI field with a file field and a non-file-supporting
   provider is rejected

**File type constraints (OpenAI):**
- Images (embedded): `.gif, .jpg, .jpeg, .png, .webp` (max ~45 MB total)
- Documents (uploaded): `.csv, .doc, .docx, .html, .json, .md, .pdf, .pptx, .txt, .tex, .xlsx, .xls` (max 512 MB, configurable via `BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB`)

## Value generation

### 7. Single cell generation

1. Click an empty AI field cell → a **Generate** button appears
2. Click Generate → value is produced for that row only
3. On a populated cell, click to edit → a **Regenerate** button appears
4. Click Regenerate → value is replaced

### 8. Bulk generation

1. Right-click the AI field header → **Generate values**
2. In the dialog:
   - **Scope**: choose "Entire table" or a specific view (filters apply)
   - **Skip populated**: checkbox to only fill empty cells
3. Submit → an async job starts (HTTP 202)
4. Verify: progress indicator appears; values populate as the job runs
5. Verify with a filtered view: only rows matching the view's filters are
   generated

### 9. Regeneration

- Single cell: click the cell → Regenerate button (visible when cell is not empty)
- Bulk: use "Generate values" dialog without "Skip populated" → all cells are
  regenerated
- Verify: regeneration replaces existing values, not appends

## Auto-update

### 10. Auto-update behavior

1. Create an AI field with a prompt referencing another field (e.g. `Categorize: {Status}`)
2. Enable **Auto-update** and save
3. Change the value of the referenced field in a row
4. Wait ~3 seconds (debounce: `BASEROW_AI_FIELD_AUTO_UPDATE_DEBOUNCE_TIME`,
   default 3s)
5. Verify: the AI field value for that row is automatically regenerated
6. Rapidly change the referenced field multiple times → verify only one
   generation runs after the debounce settles
7. Disable auto-update → changes to referenced fields no longer trigger
   regeneration

## Error handling

### 11. Configuration errors

- Set an invalid API key at workspace level → generate → should show a clear
  error (not a stack trace)
- Select a model that doesn't exist for the provider → generation fails
  gracefully
- Use a file field with a provider that doesn't support files → rejected at save
  time

### 12. Generation errors

- If the AI model returns an unparseable response for a choice field → the cell
  remains empty, no crash
- Network timeout or provider outage → error shown, other rows continue
  generating

## Concurrency limits

### 13. Job limits

- Start a bulk generation on a field → try starting another on the same field →
  should be rejected (1 job per field)
- Start 3 generation jobs (different fields) → try a 4th → should be rejected
  (max 3 concurrent per user)
- Single-cell (row-specific) generation bypasses the per-field limit
