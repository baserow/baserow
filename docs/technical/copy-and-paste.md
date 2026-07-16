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
   matching it, and only cell-level paste ever reads it.

Everything else follows from those two answers.

## The three clipboard channels

A copy can populate up to three places:

| Channel | What it is | Who reads it |
| --- | --- | --- |
| `text/plain` | The values joined into TSV (`\t` between cells, `\n` between rows). A cell is CSV-quoted only if it contains a tab, a double quote, or a newline. | Everyone — other apps, Baserow paste, the editor. |
| `text/html` | An HTML `<table>`, for pasting into Sheets/Excel. **Not written for a single 1×1 cell** (it would fight the rich text editor). | External spreadsheet apps; the rich text editor's own paste. |
| Rich blob | `localStorage["baserow.clipboardData"] = { text: <the tsv>, json: [[ prepareRichValueForCopy() ]] }`. Carries a rich, lossless representation plus per-cell metadata (e.g. the long text `richText` flag). | Baserow **cell** paste only, and only if `text/plain` still equals the stored `text`. |

The rich blob is the important one. It is written **only** by the two Baserow
cell-selection copy paths (single cell and multi-cell). Copying while editing — a
selection inside the rich editor, or a `<textarea>` selection — never writes it,
because the cell copy handler bails on the `!editing` gate. On paste,
`getRichClipboard` compares the live `text/plain` against the stored blob (normalizing
CRLF to LF) and returns the rich JSON only on a match; any external copy, or any edit
to the clipboard text, discards it.

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
path that knows the **source** field's richness. A single 1×1 paste and the grid's
multi-cell paste both call this hook for each destination cell.

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

When you are **editing** a rich cell, paste is handled by the editor's `handlePaste`,
then ProseMirror's fallback. It has **no access to the rich blob** — only the
clipboard's `text/plain` and `text/html`:

| Source pasted into the editor | Result |
| --- | --- |
| A **multi-line** Baserow cell (CSV-quoted) | inserted **literally** — `#`, `-`, `**` stay as raw characters (rich formatting **not** rendered); blank lines are kept |
| A **single-line** Baserow cell, e.g. `**bold**` (not quoted) | **Markdown is parsed** → real bold. Accidental — see below |
| External plain-only text **with** a blank line | inserted **literally**; blank lines kept |
| External plain text, **one line**, e.g. `**bold**` | **Markdown is parsed** → real bold |
| External rich content (has `text/html`, e.g. Google Docs) | the **HTML is parsed** → headings/lists/bold survive |

> **The rich → rich in-editor case is decided by accident.** Whether a copied rich
> cell keeps its Markdown *as text* or gets *rendered* depends only on whether TSV
> quoted it: a multi-line cell is quoted and pasted literally (formatting lost); a
> single-line cell like `**bold**` is unquoted and gets Markdown-parsed. This is a
> known limitation, not a designed behavior — see the ambiguity section.

Force-plain paste (`Cmd`/`Ctrl`+`Shift`+`V`) does **not** change the quoted-cell or
blank-line cases (the handler ignores the plain flag); it only stops Markdown parsing
in the single-line-external case.

### In-editor paste (plain field)

A plain long text cell is a `<textarea>`, so pasting while editing it is the plain
browser paste: the raw `text/plain` is inserted verbatim, with **no** Baserow
transform. Pasting a copied Baserow **rich** cell here therefore drops in its raw
Markdown *including* the surrounding TSV quotes and any literal `&nbsp;` sentinels.

### Which surface uses which path

| Surface | Cell selected (not editing) | While editing |
| --- | --- | --- |
| **Grid cell** | cell-level paste (rich blob available) | in-editor paste |
| **Row edit modal** field | — (no "cell selected" state) | in-editor paste, always |
| **Expanded field modal** | — | in-editor paste, always |

The row edit modal and the expanded field modal have no cell-selected state, so they
**never** reach the rich-blob cell-paste path. The grid cell-level path is the only
one that can guarantee a lossless rich → rich paste; inside those modals a copied
rich cell goes through the source-ambiguous in-editor path.

## What is distinguishable, and the core ambiguity

The whole story reduces to one question: **can the paste handler tell what the source
was?**

* **Cell-level paste can.** It reads the rich blob's `richText` flag, so it knows
  whether the copied value came from a rich or a plain field, and converts
  accordingly. This is why every cell-level case above is well-defined.
* **In-editor paste cannot.** The editor only sees `text/plain` and `text/html`; it
  never reads the `localStorage` blob. So it must guess from the text alone — and the
  text is genuinely ambiguous:

    * A rich document `[paragraph "A", empty paragraph, paragraph "B"]` serializes to
      `A\n\n\n\nB`.
    * A plain cell that literally contains those blank lines *is the same string*.
    * `\n\n` means "a paragraph break" in the first reading and "literal blank lines"
      in the second — two valid, source-dependent interpretations of identical text.

  The `&nbsp;` sentinels do **not** resolve this: they appear for *some* empty content
  (empty list items, and blank lines produced by the plain → rich conversion) but
  **not** for top-level empty paragraphs, which serialize to bare newlines. And a
  plain cell literally containing `**bold**` is indistinguishable from a rich cell
  containing bold. So the editor deliberately treats a quoted grid cell as **literal
  text** (preserving blank lines, losing Markdown rendering); a test locks this
  choice.

**The only clean disambiguator is the rich blob's `richText` flag** — the same signal
cell-level paste already uses. Exposing it to the editor would require the core rich
text editor to read the database layer's clipboard blob, inverting the module layering
(the database layer builds on core, not the reverse). And even then it would only help
while the clipboard text still matches the stored blob; an externally-touched clipboard
offers no source signal at all. That tradeoff is why the in-editor rich → rich fidelity
gap is left as-is.
