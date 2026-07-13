import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { createField } from "../../fixtures/database/field";
import {
  createFormView,
  updateFormFieldOptions,
  patchView,
} from "../../fixtures/database/view";
import { FormPage } from "../../pages/database/formPage";
import { User } from "../../fixtures/user";
import { Workspace } from "../../fixtures/workspace";

// Form view descriptions (field-level and form-level) are authored as markdown
// and rendered rich to respondents. These tests lock in the two things that
// matter on the public page: markdown becomes real formatting, and unsafe
// markdown (raw HTML / javascript: links) is rendered inert by the shared
// editor config (Markdown html:false + Link protocol allowlist).
test.describe("Form view rich-text descriptions", () => {
  test.describe.configure({ timeout: 60_000 });

  let user: User;
  let workspace: Workspace;

  test.beforeEach(async ({ workspacePage }) => {
    user = workspacePage.user;
    workspace = workspacePage.workspace;
  });

  test("renders markdown descriptions as formatting", async ({ page, goto }) => {
    const database = await createDatabase(user, "Rich Form DB", workspace);
    const table = await createTable(user, "Entries", database, [
      ["Name"],
      ["Alice"],
    ]);
    const bio = await createField(user, "Bio", "long_text", {}, table);
    const view = await createFormView(user, table);
    await patchView(user, view, {
      description: "Welcome — read the **instructions** and visit our [site](https://baserow.io).",
    });
    await updateFormFieldOptions(user, view, {
      [bio.id]: {
        enabled: true,
        required: false,
        order: 1,
        description:
          "Fill in your **bio**. See the [guide](https://baserow.io).\n\n- Be concise\n- Be honest",
      },
    });

    const formPage = new FormPage({ page, goto });
    await formPage.gotoPublic(view.slug);

    const fieldDesc = page.locator(".form-view__field-description").first();
    await fieldDesc.waitFor({ state: "visible" });
    await expect(fieldDesc.locator("strong")).toHaveCount(1);
    await expect(
      fieldDesc.locator('a[href="https://baserow.io"]'),
    ).toHaveCount(1);
    expect(await fieldDesc.locator("ul li").count()).toBeGreaterThanOrEqual(2);

    const formDesc = page.locator(".form-view__description").first();
    await expect(formDesc.locator("strong")).toHaveCount(1);
    await expect(
      formDesc.locator('a[href="https://baserow.io"]'),
    ).toHaveCount(1);
  });

  test("renders unsafe markdown inert (no script, no javascript: link)", async ({
    page,
    goto,
  }) => {
    const database = await createDatabase(user, "XSS Form DB", workspace);
    const table = await createTable(user, "Entries", database, [
      ["Name"],
      ["Bob"],
    ]);
    const bio = await createField(user, "Bio", "long_text", {}, table);
    const view = await createFormView(user, table);
    await updateFormFieldOptions(user, view, {
      [bio.id]: {
        enabled: true,
        required: false,
        order: 1,
        description:
          "<script>window.__xss = 1</script> **safe** [bad](javascript:alert(1)) [good](https://baserow.io)",
      },
    });

    let dialogFired = false;
    page.on("dialog", async (d) => {
      dialogFired = true;
      await d.dismiss();
    });

    const formPage = new FormPage({ page, goto });
    await formPage.gotoPublic(view.slug);

    const fieldDesc = page.locator(".form-view__field-description").first();
    await fieldDesc.waitFor({ state: "visible" });

    // The injected script neither executed nor was rendered as an element.
    expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();
    expect(dialogFired).toBe(false);
    await expect(fieldDesc.locator("script")).toHaveCount(0);
    // The javascript: link was dropped, not rendered as a clickable anchor.
    await expect(fieldDesc.locator('a[href^="javascript:"]')).toHaveCount(0);
    // Safe markdown still renders (bold + the https link survive).
    await expect(fieldDesc.locator("strong")).toHaveCount(1);
    await expect(
      fieldDesc.locator('a[href="https://baserow.io"]'),
    ).toHaveCount(1);
  });
});
