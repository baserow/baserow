import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createField } from "../../fixtures/database/field";
import { createTable, Table } from "../../fixtures/database/table";
import {
  createViewGroupBy,
  getDefaultGridView,
} from "../../fixtures/database/view";
import {
  createRows,
  deleteRows,
  listRows,
  updateRows,
} from "../../fixtures/database/rows";

test.describe("Grid view group-by collapse", () => {
  test("shows group value and count in the primary field area and toggles rows", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByCollapse",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "Modernize logo", Category: "Design" },
      { Name: "User portal", Category: "Development" },
      { Name: "Barcode app", Category: "Development" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    const firstHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Design" });
    await expect(firstHeader).toHaveCount(1);
    await expect(
      firstHeader.locator(".grid-view__group-header-count"),
    ).toHaveText("2");

    const countBox = await firstHeader
      .locator(".grid-view__group-header-count")
      .boundingBox();
    const categoryHeaderBox = await page
      .locator(".grid-view__right .grid-view__head")
      .getByText("Category")
      .boundingBox();
    expect(countBox).not.toBeNull();
    expect(categoryHeaderBox).not.toBeNull();
    expect(countBox!.x).toBeLessThan(categoryHeaderBox!.x);

    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();

    await firstHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toHaveCount(0);
    await expect(page.getByText("User portal")).toBeVisible();

    await firstHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();
  });

  test("keeps collapsed sibling headers visible when only the first group has rows", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByAllButFirstCollapsed",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "Modernize logo", Category: "Design" },
      { Name: "User portal", Category: "Development" },
      { Name: "Barcode app", Category: "Development" },
      { Name: "Customer journey", Category: "Research" },
      { Name: "Paid ads", Category: "Marketing" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Development" })
      .locator(".grid-view__group-header-toggle")
      .click();
    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Research" })
      .locator(".grid-view__group-header-toggle")
      .click();
    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Marketing" })
      .locator(".grid-view__group-header-toggle")
      .click();

    await page.reload();

    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();

    const headers = page.locator(".grid-view__right .grid-view__group-header");
    await expect(headers.filter({ hasText: "Design" })).toBeVisible();
    await expect(headers.filter({ hasText: "Development" })).toBeVisible();
    await expect(headers.filter({ hasText: "Research" })).toBeVisible();
    await expect(headers.filter({ hasText: "Marketing" })).toBeVisible();
  });

  test("renders nested group-by with two sticky levels and isolates collapse to the right child", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByNested",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );
    const priorityField = await createField(
      workspacePage.user,
      "Priority",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design", Priority: "High" },
      { Name: "Modernize logo", Category: "Design", Priority: "Low" },
      { Name: "User portal", Category: "Development", Priority: "High" },
      { Name: "Barcode app", Category: "Development", Priority: "High" },
      { Name: "Auth refactor", Category: "Development", Priority: "Low" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);
    await createViewGroupBy(workspacePage.user, view, priorityField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    const stickyHeaders = page.locator(
      ".grid-view__right .grid-view__sticky-group-header",
    );
    // The sticky stack should contain one header per group-by depth.
    await expect(stickyHeaders).toHaveCount(2);
    await expect(stickyHeaders.nth(0)).toContainText("Category");
    await expect(stickyHeaders.nth(0)).toContainText("Design");
    await expect(stickyHeaders.nth(1)).toContainText("Priority");

    // Collapsing the depth-1 "High" header inside Design should hide Design's
    // High row but leave Design's Low row visible — and must not affect
    // Development's High group.
    const designHighHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "High" })
      .first();
    await designHighHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toBeVisible();
    await expect(page.getByText("User portal")).toBeVisible();
    await expect(page.getByText("Barcode app")).toBeVisible();

    // Re-expanding restores the row.
    await designHighHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toBeVisible();
  });

  test("collapsing the parent hides every child of that parent", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByParentCollapse",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );
    const priorityField = await createField(
      workspacePage.user,
      "Priority",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design", Priority: "High" },
      { Name: "Modernize logo", Category: "Design", Priority: "Low" },
      { Name: "User portal", Category: "Development", Priority: "High" },
      { Name: "Barcode app", Category: "Development", Priority: "Low" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);
    await createViewGroupBy(workspacePage.user, view, priorityField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    // Wait for initial render.
    await expect(page.getByText("Rebranding website")).toBeVisible();

    const designHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Design" })
      .first();
    await designHeader.locator(".grid-view__group-header-toggle").click();

    // All depth-1 children of Design and their rows should be gone, and
    // Development's children should remain.
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toHaveCount(0);
    await expect(page.getByText("User portal")).toBeVisible();
    await expect(page.getByText("Barcode app")).toBeVisible();
  });

  test.describe("realtime row mutations keep the tree consistent", () => {
    // Helpers shared across the realtime tests. Each test seeds fresh
    // data because realtime mutations should be observed against a known
    // baseline.
    const seed = async (workspacePage: any) => {
      const database = await createDatabase(
        workspacePage.user,
        "GroupByRealtime",
        workspacePage.workspace,
      );
      const table: Table = await createTable(
        workspacePage.user,
        "Projects",
        database,
      );
      const categoryField = await createField(
        workspacePage.user,
        "Category",
        "text",
        {},
        table,
      );
      const view = await getDefaultGridView(workspacePage.user, table);
      await createViewGroupBy(workspacePage.user, view, categoryField);
      return { database, table, categoryField, view };
    };

    // Wait until the page has subscribed to the table's realtime
    // channel. Without this, API mutations triggered immediately after
    // page.goto race the page_add WS message and the rows_updated /
    // rows_created event gets dropped.
    const waitForTableSubscription = async (page: any) => {
      await page.waitForFunction(
        () => {
          const realtime = (window as any).__baserowRealtime;
          return (
            realtime &&
            realtime.pages.some((p: { page: string }) => p.page === "table")
          );
        },
        { timeout: 10000 },
      );
    };

    test("realtime row creation in an expanded group renders inside it and bumps the count", async ({
      page,
      workspacePage,
    }) => {
      const { database, table } = await seed(workspacePage);
      await createRows(workspacePage.user, table, [
        { Name: "Existing one", Category: "Design" },
        { Name: "Existing two", Category: "Design" },
      ]);

      await page.goto(`/database/${database.id}/table/${table.id}`);
      const designHeader = page
        .locator(".grid-view__right .grid-view__group-header")
        .filter({ hasText: "Design" });
      await expect(designHeader).toHaveCount(1);
      await expect(
        designHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("2");
      await waitForTableSubscription(page);

      // Realtime create from an off-page client.
      await createRows(workspacePage.user, table, [
        { Name: "Brand new design row", Category: "Design" },
      ]);

      await expect(page.getByText("Brand new design row")).toBeVisible();
      await expect(
        designHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("3");
    });

    test("realtime row creation in a collapsed group does not break into the neighbouring expanded group", async ({
      page,
      workspacePage,
    }) => {
      const { database, table } = await seed(workspacePage);
      await createRows(workspacePage.user, table, [
        { Name: "A row", Category: "Accounting" },
        { Name: "Another a row", Category: "Accounting" },
        { Name: "Dev row", Category: "Development" },
      ]);

      await page.goto(`/database/${database.id}/table/${table.id}`);

      // Collapse Development so the new row's group is hidden.
      const devHeader = page
        .locator(".grid-view__right .grid-view__group-header")
        .filter({ hasText: "Development" });
      await devHeader.locator(".grid-view__group-header-toggle").click();
      await expect(page.getByText("Dev row")).toHaveCount(0);
      await waitForTableSubscription(page);

      await createRows(workspacePage.user, table, [
        { Name: "New collapsed dev row", Category: "Development" },
      ]);

      // The new row must NOT appear inside Accounting (the only expanded
      // group). Bug fingerprint: row inserted at the sorted position
      // landed in Accounting's pixel range and rendered there.
      await expect(page.getByText("New collapsed dev row")).toHaveCount(0);
      // Development's count must reflect the new row though.
      await expect(
        devHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("2");

      // Expanding Development should now reveal the new row at the
      // correct position.
      await devHeader.locator(".grid-view__group-header-toggle").click();
      await expect(page.getByText("New collapsed dev row")).toBeVisible();
    });

    test("realtime update of a row's group-by value moves the row into the new group and prunes the old one when emptied", async ({
      page,
      workspacePage,
    }) => {
      const { database, table } = await seed(workspacePage);
      const created = await createRows(workspacePage.user, table, [
        { Name: "Solo design", Category: "Design" },
        { Name: "Dev one", Category: "Development" },
        { Name: "Dev two", Category: "Development" },
      ]);
      const soloDesignId = created[0].id;

      await page.goto(`/database/${database.id}/table/${table.id}`);
      await expect(
        page
          .locator(".grid-view__right .grid-view__group-header")
          .filter({ hasText: "Design" }),
      ).toHaveCount(1);
      await waitForTableSubscription(page);

      await updateRows(workspacePage.user, table, [
        { id: soloDesignId, Category: "Development" },
      ]);

      // Design had a single row — it must disappear once that row leaves.
      await expect(
        page
          .locator(".grid-view__right .grid-view__group-header")
          .filter({ hasText: "Design" }),
      ).toHaveCount(0);
      // The row now lives under Development; count went from 2 to 3.
      const devHeader = page
        .locator(".grid-view__right .grid-view__group-header")
        .filter({ hasText: "Development" });
      await expect(
        devHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("3");
      await expect(page.getByText("Solo design")).toBeVisible();
    });

    test("realtime update creating a brand-new group appears as a collapsed banner with the correct count", async ({
      page,
      workspacePage,
    }) => {
      const { database, table } = await seed(workspacePage);
      const created = await createRows(workspacePage.user, table, [
        { Name: "Will move", Category: "Design" },
        { Name: "Stays", Category: "Design" },
      ]);
      const willMoveId = created[0].id;

      await page.goto(`/database/${database.id}/table/${table.id}`);
      // Confirm the only group is Design before we move the row.
      await expect(
        page.locator(".grid-view__right .grid-view__group-header"),
      ).toHaveCount(1);
      await waitForTableSubscription(page);

      await updateRows(workspacePage.user, table, [
        { id: willMoveId, Category: "Marketing" },
      ]);

      // The brand-new Marketing group must materialise — earlier the row
      // disappeared because nothing in the heightIndex anchored it.
      const marketingHeader = page
        .locator(".grid-view__right .grid-view__group-header")
        .filter({ hasText: "Marketing" });
      await expect(marketingHeader).toHaveCount(1);
      await expect(
        marketingHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("1");
      // Collapsed by default — the moved row should not be visible until
      // the user explicitly expands the new group.
      await expect(marketingHeader).toHaveClass(
        /grid-view__group-header--collapsed/,
      );
      await expect(page.getByText("Will move")).toHaveCount(0);

      // Expanding the new group reveals the moved row.
      await marketingHeader
        .locator(".grid-view__group-header-toggle")
        .click();
      await expect(page.getByText("Will move")).toBeVisible();
    });

    test("boolean group-by: flipping the lone row in one group prunes that group and leaves a single header", async ({
      page,
      workspacePage,
    }) => {
      // Minimum reproducer for the "the empty group sticks around" bug:
      // group by a boolean field with one row of each value, then flip
      // the false row to true. Result must be a single ``true`` header
      // with count 2 — the now-empty ``false`` group must be removed.
      const database = await createDatabase(
        workspacePage.user,
        "GroupByBooleanFlip",
        workspacePage.workspace,
      );
      const table: Table = await createTable(
        workspacePage.user,
        "Tasks",
        database,
      );
      const completedField = await createField(
        workspacePage.user,
        "Completed",
        "boolean",
        {},
        table,
      );
      const created = await createRows(workspacePage.user, table, [
        { Name: "Done task", Completed: true },
      ]);
      // ``createTable`` seeds two empty example rows whose ``Completed``
      // defaults to ``false``, so the table starts out with three false-
      // group rows and one true-group row. Flipping ``Done task`` to
      // ``Completed: false`` empties the true group entirely — that's
      // the case the user reported (last row of a group leaves; the
      // empty banner must disappear).
      const doneId = created[0].id;

      const view = await getDefaultGridView(workspacePage.user, table);
      await createViewGroupBy(workspacePage.user, view, completedField);

      await page.goto(`/database/${database.id}/table/${table.id}`);

      const headers = page.locator(
        ".grid-view__right .grid-view__group-header",
      );
      // Two group headers initially — one per boolean value.
      await expect(headers).toHaveCount(2);
      await waitForTableSubscription(page);

      // Flip the only ``true`` row to ``false`` via a separate API
      // client so the grid only learns about it through the WS event.
      await updateRows(workspacePage.user, table, [
        { id: doneId, Completed: false },
      ]);

      // The ``true`` group is now empty; it must be pruned. The
      // remaining ``false`` header should hold every row (3 rows = 2
      // example rows seeded by ``createTable`` + the one we just
      // flipped).
      await expect(headers).toHaveCount(1);
      await expect(
        headers.first().locator(".grid-view__group-header-count"),
      ).toHaveText("3");
    });

    test("boolean group-by: exactly 2 groups with 1 row each, flipping one moves the row and prunes its old group", async ({
      page,
      workspacePage,
    }) => {
      // The exact scenario: a clean table with one ``true`` row and one
      // ``false`` row (no example seed rows). Flipping the ``false`` row
      // to ``true`` must end with a single ``true`` group containing
      // both rows. The ``false`` group, now empty, must disappear from
      // the heightIndex.
      const database = await createDatabase(
        workspacePage.user,
        "GroupByBooleanFlipPair",
        workspacePage.workspace,
      );
      const table: Table = await createTable(
        workspacePage.user,
        "Tasks",
        database,
      );
      const completedField = await createField(
        workspacePage.user,
        "Completed",
        "boolean",
        {},
        table,
      );
      // ``createTable`` always seeds two empty example rows. Drop them
      // so the test starts from a known clean state, otherwise the
      // ``false`` group would already contain the seed rows and the
      // test wouldn't be checking what we think it's checking.
      const seeded = await listRows(workspacePage.user, table);
      if (seeded.length > 0) {
        await deleteRows(
          workspacePage.user,
          table,
          seeded.map((r) => r.id),
        );
      }

      const created = await createRows(workspacePage.user, table, [
        { Name: "Pending task", Completed: false },
        { Name: "Done task", Completed: true },
      ]);
      const pendingId = created[0].id;

      const view = await getDefaultGridView(workspacePage.user, table);
      await createViewGroupBy(workspacePage.user, view, completedField);

      await page.goto(`/database/${database.id}/table/${table.id}`);

      const headers = page.locator(
        ".grid-view__right .grid-view__group-header",
      );
      // Initial state: exactly two group headers, each with count 1.
      await expect(headers).toHaveCount(2);
      const counts = headers.locator(".grid-view__group-header-count");
      await expect(counts.nth(0)).toHaveText("1");
      await expect(counts.nth(1)).toHaveText("1");

      await waitForTableSubscription(page);

      // Flip the ``false`` row → ``true`` from a separate API client so
      // the only change the page sees is the WS event.
      await updateRows(workspacePage.user, table, [
        { id: pendingId, Completed: true },
      ]);

      // After the flip, the ``false`` group is empty and must be
      // pruned; only the ``true`` group remains, now holding both rows.
      await expect(headers).toHaveCount(1);
      await expect(
        headers.first().locator(".grid-view__group-header-count"),
      ).toHaveText("2");
      // The remaining header is the ``true`` one.
      await expect(
        headers.first().locator(".card-boolean--true"),
      ).toHaveCount(1);
    });

    test("nested group-by (single-select + boolean): assigning a category to an empty-group row moves the row out of (Empty) and into the assigned category", async ({
      page,
      workspacePage,
    }) => {
      // Reproducer for the bug shown in the user's screenshot: a row
      // that lives in the (Empty) > Completed=true sub-group has its
      // Category assigned to "Development". The row must leave the
      // (Empty) section entirely and surface only under Development >
      // Completed=true — never under both, never lingering at its old
      // (Empty)>Completed=true buffer slot.
      const database = await createDatabase(
        workspacePage.user,
        "GroupByNestedSingleSelectBool",
        workspacePage.workspace,
      );
      const table: Table = await createTable(
        workspacePage.user,
        "Projects",
        database,
      );
      // Create a single-select Category field with two options.
      const categoryField = await createField(
        workspacePage.user,
        "Category",
        "single_select",
        {
          select_options: [
            { value: "Development", color: "red" },
            { value: "Marketing", color: "green" },
          ],
        },
        table,
      );
      const completedField = await createField(
        workspacePage.user,
        "Completed",
        "boolean",
        {},
        table,
      );

      // Wipe the example seed rows so we know exactly what's in the
      // table.
      const seeded = await listRows(workspacePage.user, table);
      if (seeded.length > 0) {
        await deleteRows(
          workspacePage.user,
          table,
          seeded.map((r) => r.id),
        );
      }

      // Two rows in (Empty) > Completed=true, one in
      // Development > Completed=true.
      const created = await createRows(workspacePage.user, table, [
        { Name: "Empty done one", Completed: true },
        { Name: "Empty done two", Completed: true },
        { Name: "Dev done", Category: "Development", Completed: true },
      ]);
      const target = created[0];

      const view = await getDefaultGridView(workspacePage.user, table);
      await createViewGroupBy(workspacePage.user, view, categoryField);
      await createViewGroupBy(workspacePage.user, view, completedField);

      await page.goto(`/database/${database.id}/table/${table.id}`);
      const headers = page.locator(
        ".grid-view__right .grid-view__group-header",
      );
      // Two depth-0 headers initially: Development (1) and (Empty) (2).
      await expect(
        headers.filter({ hasText: "Development" }).first(),
      ).toHaveCount(1);
      await expect(headers.filter({ hasText: "Empty" })).toHaveCount(1);

      // Expand the depth-0 (Empty) so its depth-1 sub-groups render,
      // then expand the depth-1 Completed=true so the target row is
      // visible at the top of (Empty) → Completed=true.
      const expandIfCollapsed = async (header: any) => {
        const collapsed = await header.evaluate((el: HTMLElement) =>
          el.classList.contains("grid-view__group-header--collapsed"),
        );
        if (collapsed) {
          await header.locator(".grid-view__group-header-toggle").click();
        }
      };
      const emptyHeader = headers.filter({ hasText: "Empty" }).first();
      await expandIfCollapsed(emptyHeader);
      // After (Empty) is expanded, its depth-1 children render — find
      // and expand the Completed=true one (rendered with the check icon).
      const emptyTrueHeader = page.locator(
        ".grid-view__right .grid-view__group-header:has(.card-boolean--true)",
      );
      await expect(emptyTrueHeader).toHaveCount(1);
      await expandIfCollapsed(emptyTrueHeader);
      await expect(page.getByText("Empty done one")).toBeVisible();
      await waitForTableSubscription(page);

      // Assign Development to the first (Empty) row via the API.
      await updateRows(workspacePage.user, table, [
        { id: target.id, Category: "Development" },
      ]);

      // The row name must no longer appear under (Empty)'s subtree.
      // Locate the (Empty)'s expanded section by its banner and assert
      // none of its rendered rows match the moved row.
      // Simpler: globally, the row text must appear at most once.
      await expect(page.getByText("Empty done one")).toHaveCount(1);

      // (Empty)'s count is now 1 (only "Empty done two" left).
      await expect(
        emptyHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("1");
      // Development's count is now 2 (was 1; the moved row joined).
      const developmentHeader = headers.filter({ hasText: "Development" });
      await expect(
        developmentHeader.locator(".grid-view__group-header-count"),
      ).toHaveText("2");
    });

    test("nested group-by (single-select + boolean): switching a row's Category from Accounting to null while both depth-0 groups are expanded moves the row into the (Empty) section", async ({
      page,
      workspacePage,
    }) => {
      const database = await createDatabase(
        workspacePage.user,
        "GroupByAccountingEmptyNested",
        workspacePage.workspace,
      );
      const table: Table = await createTable(
        workspacePage.user,
        "Projects",
        database,
      );
      const categoryField = await createField(
        workspacePage.user,
        "Category",
        "single_select",
        {
          select_options: [
            { value: "Accounting", color: "yellow" },
            { value: "Development", color: "red" },
          ],
        },
        table,
      );
      const completedField = await createField(
        workspacePage.user,
        "Completed",
        "boolean",
        {},
        table,
      );
      const seeded = await listRows(workspacePage.user, table);
      if (seeded.length > 0) {
        await deleteRows(
          workspacePage.user,
          table,
          seeded.map((r) => r.id),
        );
      }
      const created = await createRows(workspacePage.user, table, [
        {
          Name: "Acct done one",
          Category: "Accounting",
          Completed: true,
        },
        {
          Name: "Acct done two",
          Category: "Accounting",
          Completed: true,
        },
        {
          Name: "Acct todo",
          Category: "Accounting",
          Completed: false,
        },
        { Name: "Empty done", Category: null, Completed: true },
        { Name: "Empty todo", Category: null, Completed: false },
      ]);
      const targetId = created[0].id;

      const view = await getDefaultGridView(workspacePage.user, table);
      await createViewGroupBy(workspacePage.user, view, categoryField);
      await createViewGroupBy(workspacePage.user, view, completedField);

      await page.goto(`/database/${database.id}/table/${table.id}`);
      const headers = page.locator(
        ".grid-view__right .grid-view__group-header",
      );
      await expect(
        headers.filter({ hasText: "Accounting" }),
      ).toHaveCount(1);
      await expect(headers.filter({ hasText: "Empty" })).toHaveCount(1);

      // Expand every collapsed group, depth-0 first then depth-1, so
      // every leaf section shows its rows.
      while (true) {
        const stillCollapsed = page.locator(
          ".grid-view__right .grid-view__group-header--collapsed",
        );
        const n = await stillCollapsed.count();
        if (n === 0) break;
        await stillCollapsed
          .first()
          .locator(".grid-view__group-header-toggle")
          .click();
        await page.waitForTimeout(200);
      }

      await expect(page.getByText("Acct done one")).toBeVisible();
      await expect(page.getByText("Empty done")).toBeVisible();
      await waitForTableSubscription(page);

      // Move the target row out of Accounting → into the (Empty) group.
      await updateRows(workspacePage.user, table, [
        { id: targetId, Category: null },
      ]);

      // Counts must update: Accounting 3→2, (Empty) 2→3.
      await expect(
        headers
          .filter({ hasText: "Accounting" })
          .first()
          .locator(".grid-view__group-header-count"),
      ).toHaveText("2");
      await expect(
        headers
          .filter({ hasText: "Empty" })
          .first()
          .locator(".grid-view__group-header-count"),
      ).toHaveText("3");
      // Row must surface inside the (Empty) section — not lost.
      await expect(page.getByText("Acct done one")).toBeVisible();
    });

    test("realtime deletion of the last row in a group removes the empty group banner", async ({
      page,
      workspacePage,
    }) => {
      const { database, table } = await seed(workspacePage);
      const created = await createRows(workspacePage.user, table, [
        { Name: "Lonely", Category: "Research" },
        { Name: "Dev one", Category: "Development" },
        { Name: "Dev two", Category: "Development" },
      ]);
      const lonelyId = created[0].id;

      await page.goto(`/database/${database.id}/table/${table.id}`);
      const researchHeader = page
        .locator(".grid-view__right .grid-view__group-header")
        .filter({ hasText: "Research" });
      await expect(researchHeader).toHaveCount(1);
      await waitForTableSubscription(page);

      await deleteRows(workspacePage.user, table, [lonelyId]);

      // Empty group should be pruned, not stick around as a 0-row banner.
      await expect(researchHeader).toHaveCount(0);
      // Development is unaffected.
      await expect(
        page
          .locator(".grid-view__right .grid-view__group-header")
          .filter({ hasText: "Development" }),
      ).toHaveCount(1);
    });
  });

  test("collapse state survives a page reload", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByCollapsePersistence",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "Modernize logo", Category: "Design" },
      { Name: "User portal", Category: "Development" },
      { Name: "Barcode app", Category: "Development" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    const designHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Design" });
    await designHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);

    await page.reload();

    await expect(page.getByText("User portal")).toBeVisible();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toHaveCount(0);
  });
});
