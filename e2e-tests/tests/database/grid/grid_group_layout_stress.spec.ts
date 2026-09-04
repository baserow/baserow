import { expect, test } from "../../baserowTest";
import { createRows } from "../../../fixtures/database/rows";
import {
  type GridSetupResult,
  setupGrid,
} from "../../../fixtures/database/gridSetup";
import { patchView } from "../../../fixtures/database/view";
import { GridPage } from "../../../pages/database/gridPage";
import { baserowConfig } from "../../../playwright.config";

const ROW_COUNT = 3_000;
const LEAF_GROUP_COUNT = 1_500;
const PARENT_GROUP_COUNT = 50;
const BATCH_SIZE = 200;

type LeafGroupFixture = {
  index: number;
  parentIndex: number;
  rowStart: number;
  rowCount: number;
};

type ParentGroupFixture = {
  index: number;
  leafStart: number;
  leafCount: number;
  rowStart: number;
  rowCount: number;
};

function rowsBeforeLeafGroup(index: number): number {
  return Math.floor(index / 2) * 4 + (index % 2 === 0 ? 0 : 1);
}

const PARENT_GROUPS: ParentGroupFixture[] = (() => {
  let leafStart = 0;
  return Array.from({ length: PARENT_GROUP_COUNT }, (_, index) => {
    // Alternating parent widths deliberately put leaf-group and row boundaries at
    // different offsets throughout the dataset. Each pair still contains 60
    // leaves, so 50 parents cover exactly 1,500 leaves.
    const leafCount = index % 2 === 0 ? 29 : 31;
    const rowStart = rowsBeforeLeafGroup(leafStart);
    const group = {
      index,
      leafStart,
      leafCount,
      rowStart,
      rowCount: rowsBeforeLeafGroup(leafStart + leafCount) - rowStart,
    };
    leafStart += leafCount;
    return group;
  });
})();

const LEAF_GROUPS: LeafGroupFixture[] = PARENT_GROUPS.flatMap((parent) =>
  Array.from({ length: parent.leafCount }, (_, offset) => {
    const index = parent.leafStart + offset;
    return {
      index,
      parentIndex: parent.index,
      rowStart: rowsBeforeLeafGroup(index),
      rowCount: index % 2 === 0 ? 1 : 3,
    };
  }),
);

function padded(value: number): string {
  return String(value).padStart(4, "0");
}

function leafGroupForRow(rowIndex: number): LeafGroupFixture {
  const pairIndex = Math.floor(rowIndex / 4);
  const groupIndex = pairIndex * 2 + (rowIndex % 4 === 0 ? 0 : 1);
  const group = LEAF_GROUPS[groupIndex];
  if (group === undefined) {
    throw new Error(`No leaf group fixture for row ${rowIndex}.`);
  }
  return group;
}

test.describe("9.6 Column group layout at scale @slow", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(180_000);

  let g: GridSetupResult;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "GroupLayoutScaleDb",
      fields: [
        { name: "Cluster", type: "text" },
        { name: "Team", type: "text" },
      ],
      groupBys: [
        { fieldName: "Cluster", order: "ASC" },
        { fieldName: "Team", order: "ASC" },
      ],
    });

    for (let start = 0; start < ROW_COUNT; start += BATCH_SIZE) {
      const rows = Array.from(
        { length: Math.min(BATCH_SIZE, ROW_COUNT - start) },
        (_, offset) => {
          const index = start + offset;
          const group = leafGroupForRow(index);
          return {
            Name: `Scale row ${padded(index)}`,
            Cluster: `Cluster ${padded(group.parentIndex)}`,
            Team: `Group ${padded(group.index)}`,
          };
        },
      );
      await createRows(g.user, g.table, rows);
    }

    await patchView(g.user, g.view, {
      group_by_layout: "banner",
      row_identifier_type: "count",
    });
  });

  test("9.6.6 virtualizes, switches layouts, and reaches uneven paged boundaries across thousands of rows and groups", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failedApiResponses: string[] = [];
    const failedApiRequests: string[] = [];
    const pageErrors: string[] = [];
    const groupDataRequests: string[] = [];
    const rowDataRequests: string[] = [];
    const apiPrefix = new URL(
      "/api/",
      baserowConfig.PUBLIC_BACKEND_URL,
    ).toString();
    const groupDataPath = `/api/database/views/grid/${g.view.id}/group-by-data/`;
    const rowDataPath = `/api/database/views/grid/${g.view.id}/`;
    const rowHeight = 33;

    const expectVisibleGroupSpanCount = async (
      value: string,
      count: number,
    ) => {
      await grid.expectGroupSpanCount(value, count);
      await expect(grid.groupSpanByValue(value)).toBeVisible({
        timeout: 15_000,
      });
    };

    const expectVirtualizedDom = async () => {
      const [spanCount, leftRowCount, rightRowCount] = await Promise.all([
        page.locator(".grid-view__left .grid-view__group-span").count(),
        grid.leftRows().count(),
        grid.rightRows().count(),
      ]);
      expect(spanCount).toBeGreaterThan(0);
      expect(spanCount).toBeLessThan(100);
      expect(leftRowCount).toBeGreaterThan(0);
      expect(leftRowCount).toBeLessThan(100);
      expect(rightRowCount).toBeGreaterThan(0);
      expect(rightRowCount).toBeLessThan(100);
      expect(leftRowCount).toBe(rightRowCount);
    };

    const scrollToRow = async (index: number) => {
      const target = grid
        .leftRows()
        .filter({ hasText: `Scale row ${padded(index)}` })
        .first();
      const body = page.locator(".grid-view__left .grid-view__body");
      await page
        .locator(".grid-view__right .grid-view__body")
        .hover({ position: { x: 10, y: 10 } });
      const currentScrollTop = await body.evaluate(
        (element) => element.scrollTop,
      );
      await page.mouse.wheel(0, index * rowHeight - currentScrollTop);
      await expect(target).toBeVisible({ timeout: 15_000 });
      return target;
    };

    // Count every attempted group/row GET, including requests that a layout change
    // legitimately cancels, so the upper bounds reflect actual browser work.
    page.on("request", (request) => {
      if (request.method() !== "GET") {
        return;
      }
      const url = new URL(request.url());
      if (url.pathname === groupDataPath) {
        groupDataRequests.push(request.url());
      } else if (
        url.pathname === rowDataPath &&
        url.searchParams.has("limit")
      ) {
        rowDataRequests.push(request.url());
      }
    });
    page.on("response", (response) => {
      if (response.url().startsWith(apiPrefix) && response.status() >= 400) {
        failedApiResponses.push(`${response.status()} ${response.url()}`);
      }
    });
    page.on("requestfailed", (request) => {
      const failure = request.failure()?.errorText ?? "failed";
      // Layout changes and the final reload deliberately cancel stale virtual-row
      // prefetches. Those browser-level aborts are expected; transport failures are not.
      const wasCancelled = /ERR_ABORTED|NS_BINDING_ABORTED/i.test(failure);
      if (request.url().startsWith(apiPrefix) && !wasCancelled) {
        failedApiRequests.push(`${failure} ${request.url()}`);
      }
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    // Keep the primary field in the frozen section even when the optional assistant
    // panel is open, so the page object's primary-cell helpers remain deterministic.
    await page.setViewportSize({ width: 1_920, height: 1_080 });
    await grid.goTo(g.database, g.table);
    await grid.collapseAllGroupsFromContext();
    await grid.expectGroupByBanner(
      "Cluster 0000",
      PARENT_GROUPS[0].rowCount,
      true,
    );
    await expect(grid.leftRows()).toHaveCount(0);
    await expect(grid.rightRows()).toHaveCount(0);

    // Columns always expands the hierarchy for display, without losing the saved
    // collapse-all state that must be restored when returning to Banners.
    await grid.selectGroupLayout("Columns");
    await expectVisibleGroupSpanCount(
      "Cluster 0000",
      PARENT_GROUPS[0].rowCount,
    );
    await expectVisibleGroupSpanCount("Group 0000", LEAF_GROUPS[0].rowCount);
    await grid.expectPrimaryText(0, "Scale row 0000");
    await grid.expectRowIdentifierText(0, "1");

    await expectVirtualizedDom();

    // Exercise one- and three-row leaves, an uneven parent boundary, two sparse
    // page boundaries, and the middle of the 3,000-row dataset.
    for (const index of [40, 56, 57, 199, 200, 1_499, 1_500]) {
      const group = leafGroupForRow(index);
      const parent = PARENT_GROUPS[group.parentIndex];
      const sampledRow = await scrollToRow(index);
      // Scrolling starts over the right rows. Once the target row replaces the row
      // under the pointer, its identifier is intentionally swapped for the hover
      // checkbox, so move away before checking the count.
      await page.mouse.move(0, 0);
      await expect(
        sampledRow.locator(".grid-view__row-count-content"),
      ).toHaveText(String(index + 1));
      await expectVisibleGroupSpanCount(
        `Group ${padded(group.index)}`,
        group.rowCount,
      );
      await expectVisibleGroupSpanCount(
        `Cluster ${padded(parent.index)}`,
        parent.rowCount,
      );

      if (index === 40) {
        const parentSpan = grid.groupSpanByValue("Cluster 0000");
        const parentBox = await parentSpan.boundingBox();
        const stickyBox = await parentSpan
          .locator(".grid-view__group-cell--sticky")
          .boundingBox();
        const bodyBox = await page
          .locator(".grid-view__left .grid-view__body")
          .boundingBox();
        expect(parentBox?.height).toBe(PARENT_GROUPS[0].rowCount * rowHeight);
        expect(Math.abs((stickyBox?.y ?? 0) - (bodyBox?.y ?? 0))).toBeLessThan(
          2,
        );
      }
    }

    const finalRow = await scrollToRow(ROW_COUNT - 1);
    await page.mouse.move(0, 0);
    await expect(finalRow.locator(".grid-view__row-count-content")).toHaveText(
      String(ROW_COUNT),
    );
    await expectVisibleGroupSpanCount(
      `Group ${padded(LEAF_GROUP_COUNT - 1)}`,
      LEAF_GROUPS[LEAF_GROUP_COUNT - 1].rowCount,
    );
    await expectVisibleGroupSpanCount(
      `Cluster ${padded(PARENT_GROUP_COUNT - 1)}`,
      PARENT_GROUPS[PARENT_GROUP_COUNT - 1].rowCount,
    );

    await expectVirtualizedDom();

    await grid.selectGroupLayout("Banners");
    await grid.expectGroupByBanner(
      `Cluster ${padded(PARENT_GROUP_COUNT - 1)}`,
      PARENT_GROUPS[PARENT_GROUP_COUNT - 1].rowCount,
      true,
    );
    await expect(grid.leftRows()).toHaveCount(0);
    await expect(grid.rightRows()).toHaveCount(0);
    await expect(page.locator(".grid-view__group-span")).toHaveCount(0);

    await grid.selectGroupLayout("Columns");
    await scrollToRow(ROW_COUNT - 1);
    await grid.goTo(g.database, g.table);
    await expectVisibleGroupSpanCount(
      "Cluster 0000",
      PARENT_GROUPS[0].rowCount,
    );
    await grid.expectPrimaryText(0, "Scale row 0000");
    await grid.expectRowIdentifierText(0, "1");

    // A reload must hydrate the initial row window, then be able to jump directly
    // back into a deep sparse page without walking every preceding group.
    const deepRowIndex = 2_501;
    const deepGroup = leafGroupForRow(deepRowIndex);
    const deepParent = PARENT_GROUPS[deepGroup.parentIndex];
    const deepRow = await scrollToRow(deepRowIndex);
    await page.mouse.move(0, 0);
    await expect(deepRow.locator(".grid-view__row-count-content")).toHaveText(
      String(deepRowIndex + 1),
    );
    await expectVisibleGroupSpanCount(
      `Group ${padded(deepGroup.index)}`,
      deepGroup.rowCount,
    );
    await expectVisibleGroupSpanCount(
      `Cluster ${padded(deepParent.index)}`,
      deepParent.rowCount,
    );
    await expectVirtualizedDom();

    expect(groupDataRequests.length).toBeGreaterThan(0);
    expect(groupDataRequests.length).toBeLessThan(200);
    expect(rowDataRequests.length).toBeGreaterThan(0);
    expect(rowDataRequests.length).toBeLessThan(200);
    expect(groupDataRequests.length + rowDataRequests.length).toBeLessThan(250);
    expect(
      rowDataRequests.some((requestUrl) => {
        const offset = new URL(requestUrl).searchParams.get("offset");
        return offset !== null && Number(offset) > 1_000;
      }),
    ).toBe(true);
    expect(failedApiResponses).toEqual([]);
    expect(failedApiRequests).toEqual([]);
    expect(pageErrors).toEqual([]);
  });
});
