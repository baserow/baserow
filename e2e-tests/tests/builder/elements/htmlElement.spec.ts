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
  '<section id="widget" class="widget" aria-label="Widget" data-widget="map"><div style="height:48px"><strong onclick="this.textContent=\'Clicked\'">Widget status</strong><div data-status></div></div><img src="/html-widget-probe.png" alt="" hidden><script>window.htmlSourceScriptRan = true</script></section>';
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
  test(`HTML widgets initialize across ${mode} navigation @enterprise`, async ({
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
      const editorFrame = page.locator('iframe[title="HTML preview"]');
      await expect(editorFrame).toBeVisible();
      await expect(
        page.frameLocator('iframe[title="HTML preview"]').locator("#widget")
      ).toBeVisible();
      const hint = page.getByRole("button", {
        name: "Some embeds only display fully in Preview.",
      });
      await hint.focus();
      await expect(page.locator(".tooltip")).toHaveText(
        "Some embeds only display fully in Preview."
      );
      await hint.press("Escape");
      await page
        .locator(".html-element__editor")
        .click({ position: { x: 20, y: 8 } });
      const field = page.getByRole("textbox", { name: "HTML source" });
      if (!(await field.isVisible()))
        await builderPagePage.getElementGeneralTab();
      await expect(field).toHaveValue(html);
      await field.fill("");
      await expect(
        page.locator(".element-preview--in-error .element-preview__error-tag")
      ).toHaveText("Missing HTML content");
      await field.fill(html);
      await expect(page.locator(".element-preview--in-error")).toHaveCount(0);
      await expect(page.locator("#widget")).toHaveCount(0);
      expect(probeRequests).toBeGreaterThan(0);
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
      expect(
        await visitor.evaluate(() => Reflect.get(window, "htmlSourceScriptRan"))
      ).toBeUndefined();
      await anchor.getByText("Widget status", { exact: true }).click();
      await expect(anchor.getByText("Clicked", { exact: true })).toBeVisible();
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

test("repeated HTML is sandboxed throughout the editor @enterprise", async ({
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
    const frames = page.locator('iframe[title="HTML preview"]');
    await expect(frames).toHaveCount(2);
    for (const frame of await frames.all()) {
      await expect(frame).toHaveAttribute("sandbox", "allow-same-origin");
      await expect(frame.contentFrame().locator("#widget")).toBeVisible();
    }
    await expect(page.locator("#widget")).toHaveCount(0);
    await expect.poll(() => requests).toBeGreaterThanOrEqual(2);
  } finally {
    await deleteLicense(license);
  }
});

test("editor HTML isolates styles, blocks nested scripts and adapts its height @enterprise", async ({
  page,
  context,
  builderPagePage,
}) => {
  const license = await createLicense(ENTERPRISE_LICENSE);
  try {
    await context.route("**/html-editor-child.html", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: '<p id="child-status">Scripts blocked</p><script>document.querySelector("#child-status").textContent = "Script executed"</script>',
      })
    );
    const source =
      "<style>body { background: rgb(17, 34, 51); }</style>" +
      '<div id="editor-card" style="height:80px;color:white">Static HTML</div>' +
      '<script>document.querySelector("#editor-card").textContent = "Script executed"</script>' +
      '<iframe title="Child document" src="/html-editor-child.html" style="display:block;height:40px;border:0"></iframe>';
    await createBuilderElement(builderPagePage.builderPage, "html", {
      html: source,
    });
    await builderPagePage.goto();
    const frame = page.locator('iframe[title="HTML preview"]');
    const document = frame.contentFrame();
    await expect(document.locator("#editor-card")).toHaveText("Static HTML");
    await expect(document.locator("body")).toHaveCSS(
      "background-color",
      "rgb(17, 34, 51)"
    );
    await expect(page.locator("body")).not.toHaveCSS(
      "background-color",
      "rgb(17, 34, 51)"
    );
    await expect(
      document
        .frameLocator('iframe[title="Child document"]')
        .locator("#child-status")
    ).toHaveText("Scripts blocked");
    await expect(frame).toHaveAttribute("sandbox", "allow-same-origin");
    await expect.poll(() => frame.evaluate((el) => el.clientHeight)).toBe(120);

    // Pointer events belong to the editor, so clicking the preview selects it.
    await page
      .locator(".html-element__editor")
      .click({ position: { x: 20, y: 8 } });
    const field = page.getByRole("textbox", { name: "HTML source" });
    await expect(field).toHaveValue(source);
    await field.fill(
      '<div id="editor-card" style="height:240px">Updated HTML</div>'
    );
    await expect(document.locator("#editor-card")).toHaveText("Updated HTML");
    await expect.poll(() => frame.evaluate((el) => el.clientHeight)).toBe(240);
    await field.fill(
      '<div id="editor-card" style="height:64px">Short HTML</div>'
    );
    await expect.poll(() => frame.evaluate((el) => el.clientHeight)).toBe(64);
    await field.fill('<div style="height:900px">Tall HTML</div>');
    await expect.poll(() => frame.evaluate((el) => el.clientHeight)).toBe(600);
  } finally {
    await deleteLicense(license);
  }
});
