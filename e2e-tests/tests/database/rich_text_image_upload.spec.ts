import { test, expect } from "../baserowTest";
import { Locator } from "@playwright/test";
import { GridPage } from "../../pages/database/gridPage";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import { listRows } from "../../fixtures/database/rows";
import { createGalleryView } from "../../fixtures/database/view";
import { getClient } from "../../client";
import { baserowConfig } from "../../playwright.config";
import * as fs from "fs";
import * as path from "path";

const NOTES_FIELD_INDEX = 0;
const IMAGE_NAME = "testuploadimage.png";
const IMAGE = path.join(__dirname, "../../assets", IMAGE_NAME);
const MAX_THUMBNAIL_HEIGHT = 26;

let g: GridSetupResult;

async function uploadImage(): Promise<string> {
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(IMAGE)]), IMAGE_NAME);
  const response: any = await getClient(g.user).post(
    "user-files/upload-file/",
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data.name;
}

// Playwright cannot drive an OS file drag, so the drop is synthesized.
async function dropImageFile(target: Locator): Promise<void> {
  const base64 = fs.readFileSync(IMAGE).toString("base64");
  await target.evaluate(
    (element, { base64, name }) => {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(new File([bytes], name, { type: "image/png" }));
      const rect = element.getBoundingClientRect();
      const init = {
        bubbles: true,
        cancelable: true,
        dataTransfer,
        clientX: rect.left + rect.width / 2,
        clientY: rect.top + rect.height / 2,
      };
      for (const type of ["dragenter", "dragover", "drop"]) {
        element.dispatchEvent(new DragEvent(type, init));
      }
    },
    { base64, name: IMAGE_NAME },
  );
}

async function expectLoadedImageIn(container: Locator): Promise<void> {
  await expect
    .poll(() =>
      container
        .locator("img[src]:not(.ProseMirror-separator)")
        .evaluateAll((images) =>
          images.some(
            (image) =>
              (image as HTMLImageElement).complete &&
              (image as HTMLImageElement).naturalWidth > 0,
          ),
        ),
    )
    .toBe(true);
}

async function expectThumbnailInside(
  image: Locator,
  container: Locator,
): Promise<void> {
  await expect(image).toHaveAttribute("alt", "shot");
  await expect
    .poll(() =>
      image.evaluate(
        (element) =>
          (element as HTMLImageElement).complete &&
          (element as HTMLImageElement).naturalWidth > 0,
      ),
    )
    .toBe(true);
  await expect(async () => {
    const imageBox = (await image.boundingBox())!;
    const containerBox = (await container.boundingBox())!;
    expect(imageBox.height).toBeLessThanOrEqual(MAX_THUMBNAIL_HEIGHT);
    expect(imageBox.x).toBeGreaterThanOrEqual(containerBox.x);
    expect(imageBox.y).toBeGreaterThanOrEqual(containerBox.y);
    expect(imageBox.x + imageBox.width).toBeLessThanOrEqual(
      containerBox.x + containerBox.width,
    );
    expect(imageBox.y + imageBox.height).toBeLessThanOrEqual(
      containerBox.y + containerBox.height,
    );
  }).toPass({ timeout: 10_000 });
}

test.describe("Rich text image upload", () => {
  test.describe.configure({ timeout: 60_000 });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Rich text image upload DB",
      tableName: "Rich text image upload",
      fields: [
        {
          name: "Notes",
          type: "long_text",
          settings: { long_text_enable_rich_text: true },
        },
      ],
    });
  });

  test("uploads an image dropped into the cell editor and shows it after a reload", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "drop", Notes: "" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await dropImageFile(grid.activeRichTextEditor());
    await expectLoadedImageIn(grid.activeRichTextEditor());
    // Escape saves the rich text cell editor rather than discarding the edit.
    await page.keyboard.press("Escape");

    await expect
      .poll(async () => (await listRows(g.user, g.table))[0].Notes)
      .toMatch(/!\[testuploadimage\]\[\w+\.png\]\(http[^)]+\)/);

    await grid.goTo(g.database, g.table);
    await grid.startEditingRichTextField(0, NOTES_FIELD_INDEX);
    await expectLoadedImageIn(grid.activeRichTextEditor());
    await page.keyboard.press("Escape");

    await grid.openRowModalFromContext(0);
    await expectLoadedImageIn(grid.rowEditModal());
  });

  test("shows an image that follows text in the selected cell and on a gallery card", async ({
    page,
  }) => {
    const userFileName = await uploadImage();
    await resetRows(g, [
      { Name: "inline", Notes: `Hello ![shot][${userFileName}] after` },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.selectFieldCell(0, NOTES_FIELD_INDEX);
    await expectThumbnailInside(
      grid.selectedFieldCellAt(0, NOTES_FIELD_INDEX).locator("img"),
      grid.fieldCellAt(0, NOTES_FIELD_INDEX),
    );

    const gallery = await createGalleryView(g.user, g.table);
    await getClient(g.user).patch(`database/views/${gallery.id}/field-options/`, {
      field_options: { [g.fieldByName.Notes.id]: { hidden: false } },
    });
    const galleryUrl = new URL(
      `/database/${g.database.id}/table/${g.table.id}/${gallery.id}`,
      baserowConfig.PUBLIC_WEB_FRONTEND_URL,
    );
    galleryUrl.searchParams.set("token", g.user.refreshToken);
    await page.goto(galleryUrl.toString());
    const cardValue = page
      .locator(".gallery-view__card", { hasText: "inline" })
      .locator(".card__field", {
        has: page.locator(".card__field-name", { hasText: "Notes" }),
      })
      .locator(".card__field-value");
    await expectThumbnailInside(cardValue.locator("img"), cardValue);
  });
});
