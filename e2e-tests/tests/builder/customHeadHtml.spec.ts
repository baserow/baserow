import { getClient } from "../../client";
import { createBuilderElement } from "../../fixtures/builder/builderElement";
import { createBuilderPage } from "../../fixtures/builder/builderPage";
import { publishBuilder } from "../../fixtures/builder/domain";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

test("renders published head HTML in order and executes it once per document @enterprise", async ({
  builderPagePage,
  goto,
  page,
  workspacePage,
}) => {
  test.setTimeout(90000);
  const license = await createLicense(ENTERPRISE_LICENSE);
  try {
    const { builder, builderPage } = builderPagePage;
    const nextPage = await createBuilderPage("Next page", "/next", builder);
    await createBuilderElement(builderPage, "link", {
      value: "'Open next page'",
      navigate_to_page_id: nextPage.id,
    });
    await createBuilderElement(nextPage, "heading", {
      value: "'Reached next page'",
    });

    const publishedHead = [
      '<meta name="test-baserow-head" content="published">',
      '<script>(window.baserowHeadRuns ??= []).push("first")</script>',
      '<script type="application/ld+json">{"name":"Published page"}</script>',
      '<script>window.baserowHeadRuns.push("second")</script>',
    ].join("\n");
    const client = getClient(workspacePage.user);
    await client.patch(`applications/${builder.id}/`, {
      head_html: publishedHead,
    });

    const domainName = `e2e-head-${builder.id}.localhost`;
    await publishBuilder(builder, domainName);
    const publishedUrl = new URL(
      builderPage.path,
      baserowConfig.PUBLIC_WEB_FRONTEND_URL
    );
    publishedUrl.hostname = domainName;
    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().resourceType() === "document" &&
        response.url() === publishedUrl.href
    );
    await goto(publishedUrl.href, { waitUntil: "hydration" });
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    const documentSource = await response.text();
    expect(documentSource.match(/<head>[\s\S]*?<\/head>/)?.[0]).toContain(
      publishedHead
    );

    const headRuns = () =>
      page.evaluate(() => Reflect.get(window, "baserowHeadRuns"));
    expect(await headRuns()).toEqual(["first", "second"]);
    const marker = page.locator('head meta[name="test-baserow-head"]');
    await expect(marker).toHaveAttribute("content", "published");
    await marker.evaluate((element) => element.setAttribute("data-loaded", ""));
    await page.getByRole("link", { name: "Open next page" }).click();
    await expect(
      page.getByRole("heading", { name: "Reached next page" })
    ).toBeVisible();
    await expect(
      page.locator('head meta[name="test-baserow-head"][data-loaded]')
    ).toHaveCount(1);
    expect(await headRuns()).toEqual(["first", "second"]);

    await client.patch(`applications/${builder.id}/`, {
      head_html: '<meta name="test-baserow-head" content="draft">',
    });
    await page.reload();
    await expect(marker).toHaveAttribute("content", "published");
    expect(await headRuns()).toEqual(["first", "second"]);
  } finally {
    await deleteLicense(license);
  }
});
