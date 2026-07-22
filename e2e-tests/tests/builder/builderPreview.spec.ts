import type { Response } from "@playwright/test";

import { getClient } from "../../client";
import { createBuilderElement } from "../../fixtures/builder/builderElement";
import { createBuilder } from "../../fixtures/builder/builder";
import { createBuilderPage } from "../../fixtures/builder/builderPage";
import { createBuilderWorkflowAction } from "../../fixtures/builder/builderWorkflowAction";
import { createDatabase } from "../../fixtures/database/database";
import { getFieldsForTable } from "../../fixtures/database/field";
import { listRows } from "../../fixtures/database/rows";
import { createTable } from "../../fixtures/database/table";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

test.describe("Builder preview test suite", () => {
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
      `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/builder/${secondBuilder.id}/page/${secondBuilderPage.id}`
    );

    const secondPreviewPromise = context.waitForEvent("page");
    await page.getByRole("button", { name: "Preview" }).click();
    const secondPreview = await secondPreviewPromise;
    await expect(secondPreview.getByText(secondContent)).toBeVisible();

    await Promise.all([firstPreview.reload(), secondPreview.reload()]);
    await expect(firstPreview.getByText(firstContent)).toBeVisible();
    await expect(secondPreview.getByText(secondContent)).toBeVisible();
    await expect(firstPreview).toHaveURL(
      new RegExp(`/builder-preview/${builderPagePage.builder.id}/`)
    );
    await expect(secondPreview).toHaveURL(
      new RegExp(`/builder-preview/${secondBuilder.id}/`)
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

    const documentResponses: Response[] = [];
    const captureDocumentResponse = (response: Response) => {
      if (response.request().resourceType() === "document") {
        documentResponses.push(response);
      }
    };
    context.on("response", captureDocumentResponse);

    try {
      const previewPagePromise = context.waitForEvent("page");
      await page.getByRole("button", { name: "Preview" }).click();
      const previewPage = await previewPagePromise;
      await previewPage.waitForLoadState("domcontentloaded");

      const previewOrigin = new URL(baserowConfig.BUILDER_PREVIEW_URL).origin;
      const finalDocumentResponse = documentResponses.findLast((response) => {
        const url = new URL(response.url());
        return url.origin === previewOrigin && url.search === "";
      });
      if (!finalDocumentResponse) {
        const lastDocumentBody = await documentResponses.at(-1)?.text();
        const errorTitle = lastDocumentBody?.match(
          /<title>(.*?)<\/title>/
        )?.[1];
        throw new Error(
          `The clean preview document response was not received. Documents: ${documentResponses
            .map((response) => {
              const url = new URL(response.url());
              return `${response.status()} ${url.origin}${url.pathname}`;
            })
            .join(", ")}. Error title: ${errorTitle}`
        );
      }

      expect(finalDocumentResponse.status()).toBe(200);
      const initialHtml = await finalDocumentResponse.text();
      expect(initialHtml).toContain("<title>Default page</title>");
      expect(initialHtml).toContain(previewContent);
      await expect(previewPage).toHaveTitle("Default page");
      await expect(previewPage.getByText(previewContent)).toBeVisible();

      const missingPageResponse = await previewPage.goto(
        `${previewOrigin}/builder-preview/${builderPagePage.builderPage.builder.id}/missing-page`
      );
      expect(missingPageResponse?.status()).toBe(404);
      expect(await missingPageResponse?.text()).toContain("Page not found");
      await expect(previewPage.getByText("Page not found")).toBeVisible();
    } finally {
      context.off("response", captureDocumentResponse);
    }
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
    await previewPage.goto(grantResponse.data.url);
    await expect(
      previewPage.getByRole("button", { name: "Create preview row" })
    ).toBeVisible();

    const dispatchResponse = previewPage.waitForResponse(
      (response) =>
        response.url() ===
          `${baserowConfig.PUBLIC_BACKEND_URL}/api/builder/workflow_action/${action.id}/dispatch/` &&
        response.request().method() === "POST"
    );
    await previewPage
      .getByRole("button", { name: "Create preview row" })
      .click();
    expect((await dispatchResponse).status()).toBe(200);
    expect(await listRows(user, table)).toEqual([
      expect.objectContaining({ Name: "Created from preview" }),
    ]);
  });
});
