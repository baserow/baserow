import { expect, test } from "../../baserowTest";
import { getClient } from "../../../client";
import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { createBuilderPage } from "../../../fixtures/builder/builderPage";
import { publishBuilder } from "../../../fixtures/builder/domain";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../../fixtures/licence";
import { baserowConfig } from "../../../playwright.config";
import { createDatabase } from "../../../fixtures/database/database";
import { createTable } from "../../../fixtures/database/table";
import { createLocalBaserowIntegration } from "../../../fixtures/builder/integration";

test.describe.configure({ mode: "default" });

const html =
  '<section id="widget" class="widget" aria-label="Widget" data-widget="map"><div style="height:48px"><strong>Widget status</strong><div data-status></div></div><img src="/html-widget-probe.png" alt="" hidden></section>';
const script = `
  (() => {
    window.loaderRuns = (window.loaderRuns || 0) + 1;
    const initializeWidgets = () => {
      for (const node of document.querySelectorAll('[data-widget]:not([data-initialized])')) {
        window.initializations = (window.initializations || 0) + 1;
        node.dataset.initialized = String(window.initializations);
        node.querySelector("[data-status]").textContent = "Ready";
      }
    };
    initializeWidgets();
    new MutationObserver(initializeWidgets).observe(document.documentElement, { childList: true, subtree: true });
  })();
`;

for (const mode of ["preview", "published"]) {
  test(`static HTML widgets initialize across ${mode} navigation @enterprise`, async ({
    page,
    context,
    builderPagePage,
    workspacePage,
  }, testInfo) => {
    test.setTimeout(90000);
    page.setDefaultTimeout(10000);
    const license = await createLicense(ENTERPRISE_LICENSE);
    try {
      const { builder, builderPage } = builderPagePage;
      const other = await createBuilderPage("Other", "/other", builder);
      await createBuilderElement(builderPage, "html", { html });
      await createBuilderElement(builderPage, "link", {
        value: "'Leave widget'",
        navigate_to_page_id: other.id,
      });
      await createBuilderElement(other, "link", {
        value: "'Return to widget'",
        navigate_to_page_id: builderPage.id,
      });
      const api = getClient(workspacePage.user);
      await api.patch(`applications/${builder.id}/`, {
        custom_code: { js: script },
      });

      let probeRequests = 0;
      await context.route("**/html-widget-probe.png", (route) => {
        probeRequests++;
        return route.fulfill({ status: 204 });
      });
      await builderPagePage.goto();
      const placeholder = page.getByText(
        "Custom HTML appears in preview and in the published application."
      );
      await expect(placeholder).toBeVisible();
      await placeholder.click({ position: { x: 20, y: 8 }, timeout: 8000 });
      const field = page.getByRole("textbox", { name: "HTML source" });
      if (!(await field.isVisible()))
        await builderPagePage.getElementGeneralTab();
      await expect(field).toHaveValue(html);
      await field.fill('<img src="/html-widget-probe.png" onerror="alert(1)">');
      await expect(
        page.getByText("Enter static HTML only.", { exact: false })
      ).toBeVisible();
      await field.fill(html);
      await expect(
        page.getByText("Enter static HTML only.", { exact: false })
      ).toBeHidden();
      await expect(page.locator("#widget")).toHaveCount(0);
      expect(probeRequests).toBe(0);
      await page.screenshot({ path: testInfo.outputPath("editor.png") });
      await testInfo.attach("editor", {
        path: testInfo.outputPath("editor.png"),
        contentType: "image/png",
      });

      const visitor = await context.newPage();
      if (mode === "preview") {
        const grant = await api.post(`builder/preview/${builder.id}/grant/`, {
          path: builderPage.path,
        });
        await visitor.goto(grant.data.url);
      } else {
        const domain = `html-widget-${builder.id}.localhost`;
        await publishBuilder(builder, domain);
        const url = new URL(
          builderPage.path,
          baserowConfig.PUBLIC_WEB_FRONTEND_URL
        );
        url.hostname = domain;
        await visitor.goto(url.href);
      }

      const anchor = visitor.locator(
        "#widget.widget[data-widget=map][aria-label=Widget]"
      );
      await expect(anchor).toHaveAttribute("data-initialized", "1");
      await visitor.waitForLoadState("networkidle");
      const initial = await anchor.elementHandle();
      const initialLoads = await visitor.evaluate(() =>
        Reflect.get(window, "loaderRuns")
      );
      // Global code has its own hydration lifecycle. Compare with the same
      // application loading a page without an HTML element.
      const control = await context.newPage();
      const otherUrl = await visitor
        .getByRole("link", { name: "Leave widget" })
        .evaluate((link: HTMLAnchorElement) => link.href);
      await control.goto(otherUrl, { waitUntil: "networkidle" });
      await expect(
        control.getByRole("link", { name: "Return to widget" })
      ).toBeVisible();
      expect(initialLoads).toBeGreaterThan(0);
      expect(
        await control.evaluate(() => Reflect.get(window, "loaderRuns"))
      ).toBe(initialLoads);
      await control.close();
      const host = anchor.locator("..");
      const height = () =>
        host.evaluate((el) => el.getBoundingClientRect().height);
      await expect.poll(height).toBe(48);
      await anchor.evaluate((el) => {
        const details = document.createElement("div");
        details.textContent = "Additional widget content";
        details.style.height = "96px";
        el.append(details);
      });
      await expect.poll(height).toBe(144);
      await visitor.screenshot({ path: testInfo.outputPath(mode + ".png") });
      await testInfo.attach(mode, {
        path: testInfo.outputPath(mode + ".png"),
        contentType: "image/png",
      });

      await visitor.getByRole("link", { name: "Leave widget" }).click();
      await expect(
        visitor.getByRole("link", { name: "Return to widget" })
      ).toBeVisible();
      await expect(anchor).toHaveCount(0);
      expect(await initial!.evaluate((el) => el.isConnected)).toBe(false);
      await visitor.getByRole("link", { name: "Return to widget" }).click();
      await expect(anchor).toHaveAttribute("data-initialized", "2");
      expect(
        await visitor.evaluate(() => Reflect.get(window, "loaderRuns"))
      ).toBe(initialLoads);
    } finally {
      await deleteLicense(license);
    }
  });
}

test("repeated HTML stays inert throughout the editor @enterprise", async ({
  page,
  context,
  builderPagePage,
  workspacePage,
}) => {
  const license = await createLicense(ENTERPRISE_LICENSE);
  try {
    const { builder, builderPage } = builderPagePage;
    const { user, workspace } = workspacePage;
    const database = await createDatabase(user, "Widget rows", workspace);
    const table = await createTable(user, "Widgets", database, [
      ["Name"],
      ["First"],
      ["Second"],
    ]);
    const integration = await createLocalBaserowIntegration(
      builder,
      "Widget rows"
    );
    const { data: source } = await getClient(user).post(
      `builder/page/${builderPage.id}/data-sources/`,
      {
        type: "local_baserow_list_rows",
        name: "Widgets",
        integration_id: integration.id,
        table_id: table.id,
      }
    );
    const repeat = await createBuilderElement(builderPage, "repeat", {
      data_source_id: source.id,
    });
    await createBuilderElement(builderPage, "html", {
      html,
      reference_element_id: repeat.id,
      position: "child",
    });
    let requests = 0;
    await context.route("**/html-widget-probe.png", (route) => {
      requests++;
      return route.fulfill({ status: 204 });
    });
    await builderPagePage.goto();
    await expect(
      page.getByText(
        "Custom HTML appears in preview and in the published application."
      )
    ).toHaveCount(2);
    await expect(page.locator("#widget")).toHaveCount(0);
    expect(requests).toBe(0);
  } finally {
    await deleteLicense(license);
  }
});
