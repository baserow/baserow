import {
  createDashboard,
  createSummaryWidget,
  updateDashboardWidgetLayout,
} from "../../fixtures/dashboard/dashboard";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

test("keeps unconfigured widgets visible while creating another widget", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(60_000);
  const dashboard = await createDashboard(
    "Dashboard widget creation loading",
    workspacePage.workspace
  );
  const widget = await createSummaryWidget(dashboard, "Unconfigured widget");
  await page.goto(
    `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`
  );
  const existingCard = page.getByTestId(`dashboard-widget-${widget.id}`);
  await expect(
    existingCard.locator(".dashboard-widget__configuration-status")
  ).toBeVisible();
  await page.getByText("Edit mode", { exact: true }).click();

  let releaseDispatches!: () => void;
  const dispatchesReady = new Promise<void>((resolve) => {
    releaseDispatches = resolve;
  });
  let pendingDispatches = 0;
  await page.route(
    "**/api/dashboard/data-sources/*/dispatch/",
    async (route) => {
      pendingDispatches += 1;
      await dispatchesReady;
      await route.continue();
    }
  );

  try {
    await page.getByRole("button", { name: "Add widget", exact: true }).click();
    const creationResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(`/dashboard/${dashboard.id}/widgets/`)
    );
    await page
      .locator(".create-widget-card")
      .filter({ hasText: "Summary" })
      .click();
    const createdWidget = await (await creationResponse).json();
    const newCard = page.getByTestId(`dashboard-widget-${createdWidget.id}`);
    await expect.poll(() => pendingDispatches).toBeGreaterThan(0);
    await expect(newCard).toHaveClass(/skeleton-loading/);
    await expect(existingCard).not.toHaveClass(/skeleton-loading/);
    await expect(existingCard.locator(".widget__header")).toBeVisible();
    await expect(
      existingCard.locator(".dashboard-widget__configuration-status")
    ).toBeVisible();

    releaseDispatches();
    await expect(newCard).not.toHaveClass(/skeleton-loading/);
    await expect(newCard.locator(".widget__header")).toBeVisible();
  } finally {
    releaseDispatches();
    await page.unrouteAll({ behavior: "wait" });
  }
});

for (const width of [1920, 1200, 900]) {
  test(`keeps loading widgets at their final size and position at ${width}px`, async ({
    page,
    workspacePage,
  }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width, height: 1000 });
    const dashboard = await createDashboard(
      "Dashboard loading geometry",
      workspacePage.workspace
    );
    const widgets = await Promise.all([
      createSummaryWidget(dashboard, "Small widget"),
      createSummaryWidget(dashboard, "Large widget"),
      createSummaryWidget(dashboard, "Lower widget"),
    ]);
    await updateDashboardWidgetLayout(dashboard, [
      {
        id: widgets[0].id,
        grid_x: 0,
        grid_y: 0,
        grid_width: 2,
        grid_height: 4,
      },
      {
        id: widgets[1].id,
        grid_x: 2,
        grid_y: 0,
        grid_width: 4,
        grid_height: 6,
      },
      {
        id: widgets[2].id,
        grid_x: 0,
        grid_y: 6,
        grid_width: 3,
        grid_height: 5,
      },
    ]);

    let releaseWidgets!: () => void;
    let releaseDataSources!: () => void;
    const widgetsReady = new Promise<void>((resolve) => {
      releaseWidgets = resolve;
    });
    const dataSourcesReady = new Promise<void>((resolve) => {
      releaseDataSources = resolve;
    });
    await page.route(
      `**/api/dashboard/${dashboard.id}/widgets/`,
      async (route) => {
        await widgetsReady;
        await route.continue();
      }
    );
    await page.route(
      `**/api/dashboard/${dashboard.id}/data-sources/`,
      async (route) => {
        await dataSourcesReady;
        await route.continue();
      }
    );

    try {
      await page.goto(
        `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`,
        {
          waitUntil: "domcontentloaded",
        }
      );
      await expect(
        page.getByTestId("dashboard-widget-grid-loading")
      ).toBeVisible();
      await expect(page.locator(".dashboard-widget")).toHaveCount(0);
      releaseWidgets();

      const grid = page.getByTestId("dashboard-widget-grid");
      await expect(grid).toHaveClass(/dashboard-widget-grid--layout-ready/);
      await expect(grid.locator(".loading-spinner")).toHaveCount(0);
      const cards = widgets.map((widget) =>
        page.getByTestId(`dashboard-widget-${widget.id}`)
      );
      const loadingBoxes = [];
      for (const card of cards) {
        await expect(card).toHaveClass(/skeleton-loading/);
        await expect(card).toHaveAttribute("aria-busy", "true");
        await expect(card.locator(".widget__header")).toBeHidden();
        const box = await card.boundingBox();
        if (!box) throw new Error("Could not measure the loading widget");
        const placeholder = await card.evaluate((element) => {
          const style = getComputedStyle(element, "::after");
          return {
            width: parseFloat(style.width),
            height: parseFloat(style.height),
          };
        });
        expect(placeholder.width).toBeCloseTo(box.width - 2, 0);
        expect(placeholder.height).toBeCloseTo(box.height - 2, 0);
        loadingBoxes.push(box);
      }

      releaseDataSources();
      await expect(grid.locator(".skeleton-loading")).toHaveCount(0);
      for (const [index, card] of cards.entries()) {
        await expect(card.locator(".widget__header")).toBeVisible();
        await expect(
          card.locator(".dashboard-summary-widget__summary")
        ).toBeVisible();
        await expect
          .poll(() => card.boundingBox())
          .toEqual(loadingBoxes[index]);
      }
    } finally {
      releaseWidgets();
      releaseDataSources();
      await page.unrouteAll({ behavior: "wait" });
    }
  });
}
