import { getClient } from "../../client";
import { createBuilderElement } from "../../fixtures/builder/builderElement";
import { createBuilder } from "../../fixtures/builder/builder";
import { createBuilderPage } from "../../fixtures/builder/builderPage";
import { createBuilderWorkflowAction } from "../../fixtures/builder/builderWorkflowAction";
import { createDatabase } from "../../fixtures/database/database";
import { getFieldsForTable } from "../../fixtures/database/field";
import { createRows, listRows } from "../../fixtures/database/rows";
import { createTable } from "../../fixtures/database/table";
import { createLocalBaserowIntegration } from "../../fixtures/builder/integration";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

/**
 * Run this suite from the repository root after selecting one of these URL
 * configurations in `e2e-tests/.env` (leave `CI` unset).
 *
 * Same hostname:
 *   PUBLIC_WEB_FRONTEND_URL=http://localhost:3070
 *   PUBLIC_BACKEND_URL=http://localhost:8070
 *   BASEROW_BUILDER_PREVIEW_URL=http://localhost:3070
 *
 * Sibling hostnames (all must resolve to 127.0.0.1):
 *   PUBLIC_WEB_FRONTEND_URL=http://app.getbaserow.io:3070
 *   PUBLIC_BACKEND_URL=http://app.getbaserow.io:8070
 *   BASEROW_BUILDER_PREVIEW_URL=http://preview.getbaserow.io:3070
 *
 * Then run:
 *   just e2e up
 *   just e2e test tests/builder/builderPreview.spec.ts --workers=1
 */
test.describe("Builder preview test suite", () => {
  test("loads authenticated custom CSS and JavaScript @enterprise", async ({
    context,
    builderPagePage,
    workspacePage,
  }) => {
    const license = await createLicense(ENTERPRISE_LICENSE);
    const cssMarker = "preview-css-loaded";
    const jsMarker = "preview-js-loaded";

    try {
      await getClient(workspacePage.workspace.user).patch(
        `applications/${builderPagePage.builder.id}/`,
        {
          custom_code: {
            css: `html { --preview-custom-code: ${cssMarker}; }`,
            js: `document.documentElement.dataset.previewCustomCode = "${jsMarker}";`,
          },
        }
      );
      const grantResponse = await getClient(workspacePage.workspace.user).post(
        `builder/preview/${builderPagePage.builder.id}/grant/`,
        { path: builderPagePage.builderPage.path }
      );
      const previewPage = await context.newPage();
      const customCodeResponses = Promise.all([
        previewPage.waitForResponse((response) =>
          response.url().endsWith("/custom-code/css/")
        ),
        previewPage.waitForResponse((response) =>
          response.url().endsWith("/custom-code/js/")
        ),
      ]);

      await previewPage.goto(grantResponse.data.url, {
        waitUntil: "networkidle",
      });

      for (const response of await customCodeResponses) {
        expect(response.status()).toBe(200);
      }
      await expect
        .poll(() =>
          previewPage.evaluate(() => ({
            css: getComputedStyle(document.documentElement)
              .getPropertyValue("--preview-custom-code")
              .trim(),
            js: document.documentElement.dataset.previewCustomCode,
          }))
        )
        .toEqual({ css: cssMarker, js: jsMarker });
    } finally {
      await deleteLicense(license);
    }
  });

  test("keeps simultaneous builder preview sessions isolated", async ({
    page,
    context,
    builderPagePage,
    workspacePage,
  }) => {
    const firstContent = "First builder preview";
    await createBuilderElement(builderPagePage.builderPage, "heading", {
      value: `'${firstContent}'`,
    });
    await builderPagePage.goto();

    const firstPreviewPromise = context.waitForEvent("page");
    await page.getByRole("button", { name: "Preview" }).click();
    const firstPreview = await firstPreviewPromise;
    await expect(firstPreview.getByText(firstContent)).toBeVisible();

    const secondBuilder = await createBuilder(
      "Second preview builder",
      workspacePage.workspace
    );
    const secondBuilderPage = await createBuilderPage(
      "Second page",
      "/second/page",
      secondBuilder
    );
    const secondContent = "Second builder preview";
    await createBuilderElement(secondBuilderPage, "heading", {
      value: `'${secondContent}'`,
    });
    await page.goto(
      `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/builder/${secondBuilder.id}/page/${secondBuilderPage.id}`,
      { waitUntil: "networkidle" }
    );

    const secondPreviewPromise = context.waitForEvent("page");
    await page.getByRole("button", { name: "Preview" }).click();
    const secondPreview = await secondPreviewPromise;
    await expect(secondPreview.getByText(secondContent)).toBeVisible();

    await Promise.all([firstPreview.reload(), secondPreview.reload()]);
    await expect(firstPreview.getByText(firstContent)).toBeVisible();
    await expect(secondPreview.getByText(secondContent)).toBeVisible();
    await expect(firstPreview).toHaveURL(
      new RegExp(`/builder/preview/${builderPagePage.builder.id}/`)
    );
    await expect(secondPreview).toHaveURL(
      new RegExp(`/builder/preview/${secondBuilder.id}/`)
    );
  });

  test("Renders content and missing-page errors during SSR", async ({
    page,
    context,
    builderPagePage,
  }) => {
    const previewContent = "SSR preview content";
    await createBuilderElement(builderPagePage.builderPage, "heading", {
      value: `'${previewContent}'`,
    });
    await builderPagePage.goto();

    const previewOrigin = new URL(baserowConfig.BUILDER_PREVIEW_URL).origin;
    const finalDocumentResponsePromise = context.waitForEvent("response", {
      predicate: (response) => {
        const url = new URL(response.url());
        return (
          response.request().resourceType() === "document" &&
          url.origin === previewOrigin &&
          url.search === ""
        );
      },
    });
    const previewPagePromise = context.waitForEvent("page");

    await page.getByRole("button", { name: "Preview" }).click();

    const [previewPage, finalDocumentResponse] = await Promise.all([
      previewPagePromise,
      finalDocumentResponsePromise,
    ]);
    expect(finalDocumentResponse.status()).toBe(200);
    const initialHtml = await finalDocumentResponse.text();
    expect(initialHtml).toContain("<title>Default page</title>");
    expect(initialHtml).toContain(previewContent);
    await expect(previewPage).toHaveTitle("Default page");
    await expect(previewPage.getByText(previewContent)).toBeVisible();

    const missingPageResponse = await previewPage.goto(
      `${previewOrigin}/builder/preview/${builderPagePage.builderPage.builder.id}/missing-page`
    );
    expect(missingPageResponse?.status()).toBe(404);
    expect(await missingPageResponse?.text()).toContain("Page not found");
    await expect(previewPage.getByText("Page not found")).toBeVisible();
  });

  test("dispatches an action without user source authentication", async ({
    context,
    builderPagePage,
    workspacePage,
  }) => {
    const user = workspacePage.workspace.user;
    const database = await createDatabase(
      user,
      "Preview action database",
      workspacePage.workspace
    );
    const table = await createTable(user, "Preview action table", database, [
      ["Name"],
    ]);
    const [nameField] = await getFieldsForTable(user, table);
    const integrationResponse = await getClient(user).post(
      `application/${builderPagePage.builder.id}/integrations/`,
      { type: "local_baserow", name: "Preview action integration" }
    );
    const button = await createBuilderElement(
      builderPagePage.builderPage,
      "button",
      { value: "'Create preview row'" }
    );
    const action = await createBuilderWorkflowAction(
      builderPagePage.builderPage,
      button,
      "create_row",
      "click"
    );
    await getClient(user).patch(`builder/workflow_action/${action.id}/`, {
      service: {
        type: action.properties.service.type,
        integration_id: integrationResponse.data.id,
        table_id: table.id,
        field_mappings: [
          {
            field_id: nameField.id,
            value: "'Created from preview'",
            enabled: true,
          },
        ],
      },
    });
    const grantResponse = await getClient(user).post(
      `builder/preview/${builderPagePage.builder.id}/grant/`,
      { path: builderPagePage.builderPage.path }
    );
    const previewPage = await context.newPage();
    await previewPage.goto(grantResponse.data.url, {
      waitUntil: "networkidle",
    });
    await expect(
      previewPage.getByRole("button", { name: "Create preview row" })
    ).toBeVisible();

    const dispatchResponse = previewPage.waitForResponse((response) => {
      const path = new URL(response.url()).pathname;
      return (
        response.request().method() === "POST" &&
        path.includes("workflow") &&
        path.endsWith(`/${action.id}/dispatch/`)
      );
    });
    await previewPage
      .getByRole("button", { name: "Create preview row" })
      .click();
    const response = await dispatchResponse;
    expect(new URL(response.url()).pathname).toBe(
      `/api/builder/preview/${builderPagePage.builder.id}/workflow-actions/${action.id}/dispatch/`
    );
    expect(response.status()).toBe(200);
    expect(await listRows(user, table)).toEqual([
      expect.objectContaining({ Name: "Created from preview" }),
    ]);
  });

  test("loads more table rows after SSR hydration", async ({
    context,
    builderPagePage,
    workspacePage,
  }) => {
    const user = workspacePage.workspace.user;
    const database = await createDatabase(
      user,
      "Preview pagination database",
      workspacePage.workspace
    );
    const table = await createTable(
      user,
      "Preview pagination table",
      database,
      [["Name"]]
    );
    await createRows(
      user,
      table,
      Array.from({ length: 10 }, (_, index) => ({
        Name: `Preview row ${index + 1}`,
      }))
    );
    const integration = await createLocalBaserowIntegration(
      builderPagePage.builder,
      "Preview pagination integration"
    );
    const { data: dataSource } = await getClient(user).post(
      `builder/page/${builderPagePage.builderPage.id}/data-sources/`,
      {
        type: "local_baserow_list_rows",
        name: "Preview rows",
        integration_id: integration.id,
        table_id: table.id,
      }
    );
    await createBuilderElement(builderPagePage.builderPage, "table", {
      data_source_id: dataSource.id,
      items_per_page: 5,
    });
    const grantResponse = await getClient(user).post(
      `builder/preview/${builderPagePage.builder.id}/grant/`,
      { path: builderPagePage.builderPage.path }
    );
    const previewPage = await context.newPage();

    await previewPage.goto(grantResponse.data.url, {
      waitUntil: "networkidle",
    });
    await previewPage.reload({ waitUntil: "networkidle" });

    await expect(previewPage.locator(".ab-table tbody tr")).toHaveCount(5);
    await previewPage.getByRole("button", { name: "Show more" }).click();
    await expect(previewPage.locator(".ab-table tbody tr")).toHaveCount(10);
  });
});
