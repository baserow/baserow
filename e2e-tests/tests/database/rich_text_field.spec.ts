/**
 * Rich text long_text field - storage round trips per TipTap extension.
 *
 * Each case seeds the canonical Markdown form the editor serializer produces.
 * Opening the cell editor renders the construct, and closing it again must
 * leave the stored value byte-identical: the parse/serialize pipeline may not
 * rewrite data the user did not touch.
 */

import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import { listRows } from "../../fixtures/database/rows";
import { getClient } from "../../client";

const NOTES_FIELD_INDEX = 0;

type ExtensionCase = {
  name: string;
  markdown: string;
  /** CSS selector expected inside the open TipTap editor */
  selector: string;
  /** Expected text of the first selector match (omit for void elements) */
  text?: string;
};

const EXTENSION_CASES: ExtensionCase[] = [
  { name: "heading", markdown: "# Title", selector: "h1", text: "Title" },
  {
    name: "bullet list",
    markdown: "- alpha\n- beta",
    selector: "ul li",
    text: "alpha",
  },
  {
    name: "ordered list",
    markdown: "1. one\n2. two",
    selector: "ol li",
    text: "one",
  },
  {
    name: "task list",
    markdown: "- [ ] open\n- [x] done",
    selector: 'ul[data-type="taskList"] li[data-checked="true"]',
    text: "done",
  },
  { name: "bold", markdown: "**bold**", selector: "strong", text: "bold" },
  { name: "italic", markdown: "*italic*", selector: "em", text: "italic" },
  { name: "strike", markdown: "~~gone~~", selector: "s", text: "gone" },
  { name: "underline", markdown: "++under++", selector: "u", text: "under" },
  { name: "inline code", markdown: "`code`", selector: "code", text: "code" },
  {
    name: "code block",
    markdown: "```js\nconst x = 1;\n```",
    selector: "pre code",
    text: "const x = 1;",
  },
  {
    name: "blockquote",
    markdown: "> quoted",
    selector: "blockquote",
    text: "quoted",
  },
  { name: "horizontal rule", markdown: "---", selector: "hr" },
  {
    name: "link",
    markdown: "[Baserow](https://baserow.io)",
    selector: 'a[href="https://baserow.io"]',
    text: "Baserow",
  },
  { name: "hard break", markdown: "first  \nsecond", selector: "p br" },
  {
    name: "empty paragraphs",
    markdown: "A\n\n\n\nB",
    selector: "p:nth-of-type(3)",
    text: "B",
  },
  {
    name: "leading empty paragraph",
    markdown: "&nbsp;\n\nA",
    selector: "p:nth-of-type(2)",
    text: "A",
  },
  {
    name: "trailing empty paragraph",
    markdown: "A\n\n&nbsp;",
    selector: "p:nth-of-type(2)",
    text: "",
  },
  {
    name: "literal html",
    markdown: "&lt;div&gt;kept&lt;/div&gt;",
    selector: "p",
    text: "<div>kept</div>",
  },
  {
    name: "unknown mention",
    markdown: "ping @424242",
    selector: "p",
    text: "ping @424242",
  },
  {
    name: "punctuation prose",
    markdown: "Price is 3.50 today. See item #4 and A+B=C now.",
    selector: "p",
    text: "Price is 3.50 today. See item #4 and A+B=C now.",
  },
  {
    name: "escaped list line",
    markdown: "first  \n\\- not a list",
    selector: "p",
    text: "first- not a list",
  },
  {
    name: "escaped heading line",
    markdown: "\\# not a heading",
    selector: "p",
    text: "# not a heading",
  },
];

let g: GridSetupResult;

test.describe("Rich text field", () => {
  // The extension matrix seeds one row per case; keep them all rendered at once.
  test.use({ viewport: { width: 1280, height: 1800 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Rich text DB",
      tableName: "Rich text",
      fields: [
        {
          name: "Notes",
          type: "long_text",
          settings: { long_text_enable_rich_text: true },
        },
      ],
    });
  });

  test("every extension renders in the cell editor and survives reopening", async ({
    page,
  }) => {
    await resetRows(
      g,
      EXTENSION_CASES.map((c) => ({ Name: c.name, Notes: c.markdown })),
    );
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    for (const [rowIndex, extensionCase] of EXTENSION_CASES.entries()) {
      await grid.startEditingRichTextField(rowIndex, NOTES_FIELD_INDEX);

      const target = grid
        .activeRichTextEditor()
        .locator(extensionCase.selector)
        .first();
      await expect(
        target,
        `expected "${extensionCase.name}" to render ${extensionCase.selector}`,
      ).toBeAttached();
      if (extensionCase.text !== undefined) {
        await expect(target).toHaveText(extensionCase.text);
      }

      await grid.cancelEdit();
    }

    const rows = await listRows(g.user, g.table);
    for (const [rowIndex, extensionCase] of EXTENSION_CASES.entries()) {
      expect(
        rows[rowIndex].Notes,
        `stored value for "${extensionCase.name}" must not change on reopen`,
      ).toBe(extensionCase.markdown);
    }
  });

  test("typed multi-line content is stored and re-rendered correctly", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "typed", Notes: "" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await page.keyboard.type("First line");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Second line costs 3.50 today.");
    await page.keyboard.press("Shift+Enter");
    await page.keyboard.type("wrapped line");
    await page.keyboard.press("Enter");
    await page.keyboard.type("# Typed heading");
    await page.keyboard.press("Enter");
    await grid.cancelEdit();

    // The trailing Enter leaves an empty paragraph; it must survive the save.
    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0].Notes).toBe(
        "First line\n\nSecond line costs 3.50 today.  \nwrapped line\n\n# Typed heading\n\n&nbsp;",
      );
    }).toPass({ timeout: 10_000 });

    // Typed punctuation is stored verbatim, so backend filters match it.
    const notesFieldId = g.fieldByName["Notes"].id;
    const filtered: any = await getClient(g.user).get(
      `database/rows/table/${g.table.id}/?filter__field_${notesFieldId}__contains=${encodeURIComponent("costs 3.50 today.")}`,
    );
    expect(filtered.data.count).toBe(1);

    // A fresh load must render the same content in the read-only preview.
    await grid.goTo(g.database, g.table);
    const preview = grid.fieldCellAt(0, NOTES_FIELD_INDEX);
    await expect(preview.locator("h1")).toHaveText("Typed heading");
    await expect(preview.locator("p").first()).toHaveText("First line");
    await expect(preview.locator("p br")).toBeAttached();
  });
});
