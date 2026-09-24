/**
 * Rich text images - the "user files only" invariant.
 *
 * Rich text images are Baserow user files. A plain Markdown image
 * `![alt](url)` names a host the workspace does not control, and a row can be
 * written anonymously through a form and read anonymously from a public view,
 * so an external image would be fetched by every reader. The rule is therefore:
 * `![x](url)` never renders an `<img>`, on any surface.
 *
 * Seeding the stored Markdown through the API rather than uploading keeps these
 * deterministic: no upload round trip, no real clipboard.
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
import * as fs from "fs";
import * as path from "path";

const NOTES_FIELD_INDEX = 0;

// Host that must never be contacted. Unroutable, so a real request fails loudly
// rather than silently succeeding against something that happens to exist.
const EXTERNAL = "https://external.invalid/tracker.png";

// A reference must name a user file that exists: the rows API rejects
// `![photo][made_up.png]` with ERROR_REQUEST_BODY_VALIDATION. So upload once
// and build the unresolved storage form `![alt][name]` (no `(url)` group)
// from the name the backend assigns.
const IMAGE = path.join(__dirname, "../../assets/testuploadimage.png");

let g: GridSetupResult;
let userFileName: string;

async function uploadImage(): Promise<string> {
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(IMAGE)]), "testuploadimage.png");
  const response: any = await getClient(g.user).post(
    "user-files/upload-file/",
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data.name;
}

test.describe("Rich text images", () => {
  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Rich text images DB",
      tableName: "Rich text images",
      fields: [
        {
          name: "Notes",
          type: "long_text",
          settings: { long_text_enable_rich_text: true },
        },
      ],
    });
    userFileName = await uploadImage();
  });

  // An external image must not become an `<img>` in the cell editor.
  test("never renders an external image in the cell editor", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "external", Notes: `see ![x](${EXTERNAL}) here` }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    const editor = grid.activeRichTextEditor();

    await expect(editor.locator("img[src]")).toHaveCount(0);
    await expect(editor).toContainText("x");

    await grid.cancelEdit();
  });

  // The read-only grid preview is the surface an anonymous reader of a public
  // view sees. It shows a placeholder and renders no link at all, so the URL
  // never reaches the page.
  test("never renders an external image in the grid cell preview", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "external", Notes: `see ![x](${EXTERNAL}) here` }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    const preview = grid.fieldCellAt(0, NOTES_FIELD_INDEX);
    await expect(preview.locator("img")).toHaveCount(0);
    // The preview renders links without `href` on purpose, so an unselected
    // cell is inert. What must not appear is a live href or the URL itself.
    await expect(preview.locator("a[href]")).toHaveCount(0);
    await expect(preview).not.toContainText("external.invalid");
  });

  // The invariant that actually matters: no request leaves the browser for the
  // third-party host, on any surface. A passing render assertion would not
  // catch a preload or a CSS background.
  test("issues no request to the external host", async ({ page }) => {
    await resetRows(g, [{ Name: "external", Notes: `see ![x](${EXTERNAL}) here` }]);

    const attempted: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("external.invalid")) {
        attempted.push(request.url());
      }
    });

    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await grid.cancelEdit();
    await grid.openRowModalFromContext(0);
    await page.waitForTimeout(1000);

    expect(
      attempted,
      "the page must never fetch the external image host",
    ).toEqual([]);
  });

  // Editing a cell must save an external image back as written, not as a link.
  test("keeps a stored external image unchanged on save", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "external", Notes: `![x](${EXTERNAL})` }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await page.keyboard.type(" edited");
    await grid.cancelEdit();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0].Notes).toContain(`![x](${EXTERNAL})`);
      expect(rows[0].Notes).toContain("edited");
    }).toPass({ timeout: 10_000 });
  });

  // The placeholder for an UNRESOLVED reference is not reachable from here.
  // `resolve_user_file_urls` computes URLs by path arithmetic with no DB
  // lookup, so every name that passes write validation resolves to a URL, and
  // a name that does not exist is rejected on write. The placeholder is a
  // frontend-state-only path, covered by
  // web-frontend/test/unit/core/editor/unresolvedImageReferences.spec.js.

  // Editing around a reference must carry it through the save. Serializing the
  // document used to emit the rendered text instead of the reference, losing
  // the user file name.
  test("keeps a user file reference when the cell is edited", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "reference", Notes: `![photo][${userFileName}]` }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await page.keyboard.press("End");
    await page.keyboard.type(" tail");
    await grid.cancelEdit();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0].Notes).toContain(userFileName);
      expect(rows[0].Notes).toContain("tail");
      expect(rows[0].Notes).not.toContain("🖼");
    }).toPass({ timeout: 10_000 });
  });

  // An unsafe scheme must not survive as a clickable href anywhere.
  test("renders no live href for an unsafe scheme", async ({ page }) => {
    await resetRows(g, [
      { Name: "unsafe", Notes: "![x](javascript:alert(1))" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    const editor = grid.activeRichTextEditor();

    await expect(editor.locator("img[src]")).toHaveCount(0);
    await expect(editor.locator('a[href^="javascript:"]')).toHaveCount(0);

    await grid.cancelEdit();
  });
});
