# Copy and paste

How the web-frontend moves cell values through the clipboard. First the general
mechanism that applies to every field — including why Baserow keeps a copy of the
exact value in `localStorage` — then, in detail, the **long text** field, because it
is the only one whose value is formatted differently depending on where it is copied
from and pasted into.

<!-- TOC -->

* [Mental model](#mental-model)
* [The three clipboard channels](#the-three-clipboard-channels)
* [Why the rich blob exists: recovering the exact value](#why-the-rich-blob-exists-recovering-the-exact-value)
* [Copy: what lands on the clipboard](#copy-what-lands-on-the-clipboard)
* [Paste at the cell level](#paste-at-the-cell-level)
* [The long text field](#the-long-text-field)
    * [Cell-level paste matrix](#cell-level-paste-matrix)
    * [In-editor paste matrix (rich field)](#in-editor-paste-matrix-rich-field)
    * [In-editor paste (plain field)](#in-editor-paste-plain-field)
    * [Which surface uses which path](#which-surface-uses-which-path)
* [What is distinguishable, and the core ambiguity](#what-is-distinguishable-and-the-core-ambiguity)

<!-- TOC -->

## Mental model

Two questions decide every copy/paste outcome. Answer them first, then read the
matrices.

1. **Where does the action happen?**
    * **At the cell** — the cell is *selected* (spreadsheet-style), you are not
      editing. Baserow's own handlers run and go through the field type's
      `prepareValueForCopy` / `prepareValueForPaste`.
    * **Inside the editor** — you are *editing* the cell (a text cursor is in a
      `<textarea>` or the rich text editor). Baserow's cell handlers are suppressed
      (`canKeyboardShortcut` returns `!editing`); the browser or the rich text editor
      handles the paste instead.
2. **Is there a Baserow "rich clipboard" to read?** On every **cell** copy, Baserow
   stores a rich representation of the copied cells in `localStorage`. It is the only
   thing that remembers the *source field's* type (for example, whether a copied
   long text cell was rich). It survives only until the clipboard's plain text stops
   matching it. Cell-level paste reads the whole blob; database-hosted rich text
   editors can resolve the Markdown from a matching 1×1 rich-text copy.

Everything else follows from those two answers.

## The three clipboard channels

A copy can populate up to three places:

| Channel | What it is | Who reads it |
| --- | --- | --- |
| `text/plain` | The values joined into TSV (`\t` between cells, `\n` between rows). A cell is CSV-quoted only if it contains a tab, a double quote, or a newline. | Everyone — other apps, Baserow paste, the editor. |
| `text/html` | An HTML `<table>`, for pasting into Sheets/Excel. **Not written for a single 1×1 cell** (it would fight the rich text editor). | External spreadsheet apps; the rich text editor's own paste. |
| Rich blob | `localStorage["baserow.clipboardData"] = { text: <the tsv>, json: [[ prepareRichValueForCopy() ]] }`. Carries a rich, lossless representation plus per-cell metadata (e.g. the long text `richText` flag). | Baserow cell paste, plus database-hosted rich text editors for a 1×1 rich-text copy, and only if `text/plain` still equals the stored `text`. |

The rich blob is the important one. It is written **only** by the two Baserow
cell-selection copy paths (single cell and multi-cell). Copying while editing — a
selection inside the rich editor, or a `<textarea>` selection — never writes it,
because the cell copy handler bails on the `!editing` gate. On paste,
`getRichClipboard` compares the live `text/plain` against the stored blob (normalizing
CRLF to LF) and returns the rich JSON only on a match; any external copy, or any edit
to the clipboard text, discards it.

A rich-editor copy also records the Markdown it emitted in
`localStorage["baserow.richTextEditorClipboardData"]`. This is a narrow source marker,
not a database rich blob: it carries no field metadata and cell-level paste ignores
it. Another rich editor uses it only when the browser exposes `text/plain` without the
copied ProseMirror HTML, so the Markdown can still be parsed instead of inserted as
literal text. A non-matching paste clears the marker and follows the external
plain-text path.

## Why the rich blob exists: recovering the exact value

Plain text is a **lossy projection** of a cell. For many field types the text you see
is not enough to reconstruct the exact stored value:

* A **single / multiple select** cell copies as the option **name**. If two options
  share the same name, the name alone cannot say which option it was.
* A **link to table** cell copies as the linked rows' primary text, which can collide
  between different rows.

To avoid that data loss, every field type provides *two* copy representations, and the
paste hook takes both:

* `prepareValueForCopy(field, value)` → the human-readable **text** → `text/plain`.
* `prepareRichValueForCopy(field, value)` → a **rich JSON** value carrying the exact
  data (ids and metadata) → the `localStorage` blob's `json`.
* `prepareValueForPaste(field, text, richValue)` → prefers `richValue` when it is
  present and restores the exact cell; otherwise it parses the plain `text`. The base
  implementation returns the text unchanged, so simple fields "just work" on the text
  channel and only fields with hidden identity override these hooks.

Worked example — a single select field with two options both named `Open`:

| Where the paste comes from | On the clipboard | Paste result |
| --- | --- | --- |
| Baserow → Baserow (blob matches) | `richValue = { id: 42, value: "Open", … }` | matched **by id** → the exact option 42 |
| External app, or blob no longer matches | `text = "Open"` only | matched **by name** → the *first* `Open` option (may be the wrong one) |

So the blob is what makes an in-Baserow copy/paste **exact**. A paste from outside
Baserow — or after the clipboard text changed so the blob no longer matches — falls
back to the ambiguous text and does its best (for select, match by id if the text is
numeric, else by name).

## Copy: what lands on the clipboard

| Copy action | `text/plain` | `text/html` | Rich blob |
| --- | --- | --- | --- |
| **Cell** copy, rich long text | the stored **Markdown** (TSV-quoted if multi-line) | none (1×1) / table (multi-cell) | `{ value: <Markdown>, richText: true }` |
| **Cell** copy, plain long text | the stored **plain text** (TSV-quoted if multi-line) | none (1×1) / table (multi-cell) | `{ value: <plain text>, richText: false }` |
| **Editor** copy, rich (ProseMirror selection) | **Markdown** of the selection | ProseMirror's rich HTML | *none* |
| **Editor** copy, plain (`<textarea>` selection) | the selected plain text | none | *none* |

Note the two "rich" rows differ: a rich long text value is **stored as Markdown**, so
its `text/plain` is Markdown (e.g. `# Heading`, `- item`, `**bold**`, and `&nbsp;`
sentinels for some blank lines). A plain long text value is stored — and copied — as
literal text.

## Paste at the cell level

When a cell is **selected** (not editing), paste runs
`prepareValueForPaste(field, clipboardText, richBlobCell)`, where `richBlobCell` is the
matched rich blob entry (with its `richText` flag) or `undefined`. This is the only
path that consumes the full rich value for every field type. A single 1×1 paste and
the grid's multi-cell paste both call this hook for each destination cell.

## The long text field

Rich and plain long text are the **same field type**, switched by the field's
"enable rich text" flag. The only differences that matter here:

* **Storage** — rich = Markdown; plain = literal text.
* **Editor UI** — rich = the ProseMirror rich text editor; plain = a `<textarea>`.

### Cell-level paste matrix

Target field vs. where the clipboard came from (cell selected, not editing):

| Paste target | Source: Baserow **rich** cell | Source: Baserow **plain** cell | Source: **external** app (no blob) |
| --- | --- | --- | --- |
| **Rich** field | the Markdown, verbatim — **lossless** | `plainTextToMarkdown()` (blank lines → `&nbsp;`, single newlines → hard breaks) | `plainTextToMarkdown()` |
| **Plain** field | `richMarkdownToPlainText()` — strips `&nbsp;` sentinels & hard breaks (Markdown syntax like `#`/`**` is left as-is) | the text, verbatim — **lossless** | the text, verbatim — **lossless** |

Rich → rich and plain → plain are lossless. The two cross cases convert, and rely on
the `richText` flag from the blob to pick the direction.

### In-editor paste matrix (rich field)

When you are **editing** a database rich-text field, paste is handled by the editor's
`handlePaste`, then ProseMirror's fallback. The database component gives the core
editor a resolver for a matching 1×1 rich clipboard value, without making the core
editor depend on the database module:

| Source pasted into the editor | Result |
| --- | --- |
| A Baserow **rich-text** cell (single- or multi-line) | its matching rich blob supplies the original Markdown, which is **parsed**; formatting and trailing empty-paragraph sentinels survive |
| A **multi-line plain-text** Baserow cell (CSV-quoted) | inserted **literally** — `#`, `-`, `**` stay as raw characters; blank lines are kept |
| A **single-line plain-text** Baserow cell, e.g. `**bold**` (not quoted) | **Markdown is parsed** → real bold. Ambiguous — see below |
| A **rich-editor selection** | the ProseMirror **HTML is parsed**; if the browser exposes only `text/plain`, the matching editor marker makes TipTap parse the Markdown instead |
| External plain-only text **with** a blank line | inserted **literally**; blank lines kept |
| External plain text, **one line**, e.g. `**bold**` | **Markdown is parsed** → real bold |
| External rich content (has `text/html`, e.g. Google Docs) | the **HTML is parsed** → headings/lists/bold survive |

The resolver validates the live `text/plain` against the stored TSV before using the
Markdown and accepts only a single copied cell whose `richText` flag is true. A stale
blob, a multi-cell selection, or a plain field falls through to the existing editor
paste rules.

Force-plain paste (`Cmd`/`Ctrl`+`Shift`+`V`) does **not** change the matching rich-cell,
quoted-cell, or blank-line cases (the handler ignores the plain flag); it only stops
Markdown parsing in the single-line-external case.

### In-editor paste (plain field)

A plain long text cell is a `<textarea>`, so pasting while editing it is the plain
browser paste: the raw `text/plain` is inserted verbatim, with **no** Baserow
transform. Pasting a copied Baserow **rich** cell here therefore drops in its raw
Markdown *including* the surrounding TSV quotes and any literal `&nbsp;` sentinels.

### Which surface uses which path

| Surface | Cell selected (not editing) | While editing |
| --- | --- | --- |
| **Grid cell** | cell-level paste (full rich blob available) | in-editor paste; matching 1×1 rich-text blob available through the resolver |
| **Row edit modal** field | — (no "cell selected" state) | in-editor paste; matching 1×1 rich-text blob available through the resolver |
| **Expanded field modal** | — | in-editor paste; matching 1×1 rich-text blob available through the resolver |

The row edit modal and the expanded field modal have no cell-selected state, so they
never reach the general cell-paste path. They can still parse a copied rich-text cell
losslessly because their editor receives the narrow Markdown resolver.

## What is distinguishable, and the core ambiguity

The whole story reduces to one question: **can the paste handler tell what the source
was?**

* **Cell-level paste can.** It reads the rich blob's `richText` flag, so it knows
  whether the copied value came from a rich or a plain field, and converts
  accordingly. This is why every cell-level case above is well-defined.
* **Database rich-text editors can recognize a copied rich-text cell.** Their parent
  database component checks the matching rich blob and passes only the original
  Markdown into the core editor. This keeps the module layering intact while fixing
  both quoted multi-line Markdown and visible `&nbsp;` boundary sentinels.
* **In-editor paste can recognize another Baserow rich editor.** A matching core-owned
  marker identifies Markdown copied from a rich editor when the browser omits the
  ProseMirror HTML. Plain-only input with neither matching signal remains genuinely
  ambiguous:

    * A rich document `[paragraph "A", empty paragraph, paragraph "B"]` serializes to
      `A\n\n\n\nB`.
    * A plain cell that literally contains those blank lines *is the same string*.
    * `\n\n` means "a paragraph break" in the first reading and "literal blank lines"
      in the second — two valid, source-dependent interpretations of identical text.

  The `&nbsp;` sentinels do **not** generally resolve this: they represent boundary
  empty paragraphs and some empty list content, but interior top-level empty
  paragraphs serialize to bare newlines. And a plain cell literally containing
  `**bold**` is indistinguishable from a rich cell containing bold. So the editor
  treats an unmatched quoted grid cell as **literal text** to preserve its blank
  lines.

**The rich blob's `richText` flag remains the only field-level disambiguator** — the
same signal cell-level paste and the database editor resolver use. The core editor
accepts an optional callback rather than importing the database clipboard code. The
core-owned editor marker separately covers rich-editor → rich-editor copies whose text
still matches; externally touched or otherwise unmatched clipboard content has no
source signal and follows the plain-text fallback.
