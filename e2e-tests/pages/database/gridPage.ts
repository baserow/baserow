import { expect, Locator, Page } from "@playwright/test";
import { baserowConfig } from "../../playwright.config";
import { Database } from "../../fixtures/database/database";
import { Table } from "../../fixtures/database/table";
import { User } from "../../fixtures/user";
import { View } from "../../fixtures/database/view";

/**
 * Page object for the Baserow grid view.
 *
 * ## Left / right section model
 *
 * Baserow renders the grid in two separate sections:
 *   - LEFT  - primary field cell (Name) + row controls (ID, checkbox, warning)
 *   - RIGHT - all non-primary field cells (Score, Notes, ...)
 *
 * Both sections render the same number of rows at the same visual positions.
 * Row index 0 is the topmost visible row in both sections simultaneously.
 *
 * ## Cell addressing
 *
 * All interaction methods use numeric row/field indices:
 *   - `rowIndex`   - 0-based visual position (depends on current sort)
 *   - `fieldIndex` - 0-based index into non-primary fields (right section)
 *
 * Text-based methods (expectPrimaryText, expectPrimaryVisible, ...) are provided
 * only for ASSERTIONS - not for driving clicks. Tests know the row order from
 * their own data setup, so positional access is unambiguous.
 */
export class GridPage {
  private readonly baseUrl: string;

  constructor(
    readonly page: Page,
    private readonly user: User,
  ) {
    this.baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
  }

  // -- Navigation --------------------------------------------------------------

  async goTo(database: Database, table: Table, view?: View): Promise<void> {
    const url = new URL(
      `/database/${database.id}/table/${table.id}${
        view ? `/${view.id}` : ""
      }`,
      this.baseUrl,
    );
    url.searchParams.set("token", this.user.refreshToken);

    await this.page.context().addCookies([
      {
        name: `${baserowConfig.BASEROW_FRONTEND_COOKIE_PREFIX}jwt_token`,
        value: this.user.refreshToken,
        url: this.baseUrl,
      },
    ]);
    await this.page.goto(url.toString(), { waitUntil: "domcontentloaded" });
    // Wait until Nuxt finishes hydrating. Falls back gracefully if the dev
    // server CSP blocks the function evaluation.
    await this.page
      .waitForFunction(
        () =>
          typeof (window as any).useNuxtApp === "function" &&
          !(window as any).useNuxtApp().isHydrating,
        { timeout: 15_000 },
      )
      .catch(() => {
        // CSP may block the evaluation on the dev server; the grid visibility
        // assertion below provides sufficient confirmation of hydration.
      });
    const grid = this.page.locator(".grid-view__right");
    try {
      await expect(grid).toBeVisible({ timeout: 25_000 });
    } catch (error) {
      const diagnostics = await this.navigationDiagnostics();
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Timed out waiting for the grid view to load.\n${diagnostics}\n${message}`,
      );
    }
  }

  private async navigationDiagnostics(): Promise<string> {
    const currentUrl = new URL(this.page.url());
    if (currentUrl.searchParams.has("token")) {
      currentUrl.searchParams.set("token", "<redacted>");
    }
    const title = await this.page.title().catch(() => "<unavailable>");
    const body = await this.page
      .locator("body")
      .innerText({ timeout: 1_000 })
      .catch(() => "<unavailable>");
    const bodyExcerpt = body.replace(/\s+/g, " ").trim().slice(0, 500);

    return [
      `url=${currentUrl.toString()}`,
      `title=${title}`,
      `body=${bodyExcerpt}`,
    ].join("\n");
  }

  // -- Row locators -------------------------------------------------------------

  gridRoot(): Locator {
    return this.page.locator(".grid-view").first();
  }

  /** All rows in the LEFT section (primary field + row controls) */
  leftRows(): Locator {
    return this.page.locator(
      [
        ".grid-view__left .grid-view__rows > .grid-view__row",
        ".grid-view__left .grid-view__rows > .grid-view__row-background-wrapper > .grid-view__row",
        ".grid-view__left .grid-view__group-by-rows-row > .grid-view__row",
        ".grid-view__left .grid-view__group-by-rows-row > .grid-view__row-background-wrapper > .grid-view__row",
      ].join(", "),
    );
  }

  /** All rows in the RIGHT section (non-primary fields) */
  rightRows(): Locator {
    return this.page.locator(
      [
        ".grid-view__right .grid-view__rows > .grid-view__row",
        ".grid-view__right .grid-view__rows > .grid-view__row-background-wrapper > .grid-view__row",
        ".grid-view__right .grid-view__group-by-rows-row > .grid-view__row",
        ".grid-view__right .grid-view__group-by-rows-row > .grid-view__row-background-wrapper > .grid-view__row",
      ].join(", "),
    );
  }

  /** nth row in the LEFT section (0-based) */
  leftRowAt(index: number): Locator {
    return this.leftRows().nth(index);
  }

  /** nth row in the RIGHT section (0-based) */
  rightRowAt(index: number): Locator {
    return this.rightRows().nth(index);
  }

  // -- Cell locators -------------------------------------------------------------

  /**
   * Primary field cell for the row at `rowIndex`.
   * This is the LAST column in the left section row (after the row-details column).
   */
  primaryCellAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__column").last();
  }

  /**
   * Non-primary field cell at `rowIndex`, `fieldIndex` (both 0-based).
   * `fieldIndex 0` = first non-primary field (right section, first column).
   */
  fieldCellAt(rowIndex: number, fieldIndex: number): Locator {
    return this.rightRowAt(rowIndex)
      .locator(".grid-view__column")
      .nth(fieldIndex);
  }

  singleSelectOptionAt(rowIndex: number, fieldIndex: number): Locator {
    return this.fieldCellAt(rowIndex, fieldIndex)
      .locator(".grid-field-single-select__option")
      .first();
  }

  nonPrimaryFieldHeadersByName(fieldName: string): Locator {
    return this.page.locator(
      ".grid-view__right .grid-view__head .grid-view__description-name",
      { hasText: new RegExp(`^\\s*${this.escapeRegex(fieldName)}\\s*$`) },
    );
  }

  frozenFieldHeadersByName(fieldName: string): Locator {
    return this.page.locator(
      ".grid-view__left .grid-view__head .grid-view__description-name",
      { hasText: new RegExp(`^\\s*${this.escapeRegex(fieldName)}\\s*$`) },
    );
  }

  /** The active cell editor input/textarea (visible while a cell is in edit mode) */
  activeEditor(): Locator {
    return this.page
      .locator(
        ".grid-view__cell.active input, .grid-view__cell.active textarea",
      )
      .first();
  }

  activeCellError(): Locator {
    return this.page.locator(".grid-view__cell.active .grid-view__cell-error");
  }

  /** The active rich text (TipTap) cell editor, visible while editing a rich text cell */
  activeRichTextEditor(): Locator {
    return this.page.locator(".grid-view__cell.active .tiptap.ProseMirror");
  }

  /** The selected primary field cell content for the row at `rowIndex`. */
  selectedPrimaryCellAt(rowIndex: number): Locator {
    return this.primaryCellAt(rowIndex).locator(".grid-view__cell.active");
  }

  /** The selected non-primary field cell content at `rowIndex`, `fieldIndex`. */
  selectedFieldCellAt(rowIndex: number, fieldIndex: number): Locator {
    return this.fieldCellAt(rowIndex, fieldIndex).locator(
      ".grid-view__cell.active",
    );
  }

  // -- Row-level locators (warning, checkbox) ------------------------------------

  /**
   * The warning banner (`grid-view__row-warning`) for the row at `rowIndex`.
   * The warning lives in the LEFT section row.
   */
  rowWarningAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__row-warning");
  }

  checkboxAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__row-checkbox");
  }

  checkboxNativeAt(rowIndex: number): Locator {
    return this.checkboxAt(rowIndex).locator(".checkbox__native");
  }

  multiSelectedCells(): Locator {
    return this.page.locator(
      [
        ".grid-view__column--multi-select-top",
        ".grid-view__column--multi-select-right",
        ".grid-view__column--multi-select-bottom",
        ".grid-view__column--multi-select-left",
      ].join(", "),
    );
  }

  rowEditModal(): Locator {
    return this.page.locator(".modal__box", {
      has: this.page.locator(".row-modal__title"),
    });
  }

  rowEditModalTextField(fieldName: string): Locator {
    return this.rowEditModal()
      .locator(".row-modal__field-item", { hasText: fieldName })
      .first()
      .locator("input")
      .first();
  }

  groupByBannerByValue(value: string): Locator {
    return this.page
      .locator(".grid-view__left .grid-view__group-by-banner", {
        has: this.page.locator(".grid-view__group-by-banner-value", {
          hasText: value,
        }),
      })
      .first();
  }

  groupByContextToggle(): Locator {
    return this.page
      .locator(".header__filter-link", {
        has: this.page.locator(".iconoir-book-stack"),
      })
      .first();
  }

  groupByContext(): Locator {
    return this.page.locator(".context.group-bys").first();
  }

  // -- Grid actions ------------------------------------------------------------

  /** Click "+ Add row" at the bottom of the right section */
  async addRow(): Promise<void> {
    const addRow = this.page
      .locator(".grid-view__right .grid-view__add-row")
      .first();
    await expect(addRow).toBeVisible({ timeout: 10_000 });
    await addRow.click();
  }

  async toggleGroupBy(value: string): Promise<void> {
    await this.closeOpenContexts();
    const banner = this.groupByBannerByValue(value);
    await expect(banner).toBeVisible({ timeout: 10_000 });
    await banner.locator(".grid-view__group-by-banner-toggle").click();
  }

  async openGroupByContext(): Promise<void> {
    const toggle = this.groupByContextToggle();
    await expect(toggle).toBeVisible({ timeout: 10_000 });
    await toggle.click();
    await expect(this.groupByContext()).toBeVisible({ timeout: 10_000 });
  }

  async collapseAllGroupsFromContext(): Promise<void> {
    await this.openGroupByContext();
    await this.groupByContext()
      .getByText("Collapse all", { exact: true })
      .click();
    await this.closeGroupByContext();
  }

  async expandAllGroupsFromContext(): Promise<void> {
    await this.openGroupByContext();
    await this.groupByContext()
      .getByText("Expand all", { exact: true })
      .click();
    await this.closeGroupByContext();
  }

  async addGroupBy(fieldName: string): Promise<void> {
    await this.openGroupByContext();
    await this.groupByContext()
      .getByText("choose a field to group by", { exact: true })
      .click();

    const item = this.page
      .locator(".select__items:visible .select__item", {
        hasText: this.exactTextRegex(fieldName),
      })
      .first();
    await expect(item).toBeVisible({ timeout: 10_000 });
    await item.locator(".select__item-link").click();
    await this.closeGroupByContext();
  }

  async closeGroupByContext(): Promise<void> {
    await this.closeOpenContexts();
    await expect(this.groupByContext()).toBeHidden({ timeout: 10_000 });
  }

  async closeOpenContexts(): Promise<void> {
    await this.page.keyboard.press("Escape");
    const viewport = this.page.viewportSize();
    await this.page.mouse.click(
      viewport ? viewport.width - 5 : 1000,
      viewport ? viewport.height - 5 : 700,
    );
  }

  /** Single-click a non-primary cell to select it without entering edit mode */
  async selectFieldCell(rowIndex: number, fieldIndex: number): Promise<void> {
    const cell = this.fieldCellAt(rowIndex, fieldIndex);
    const selected = this.selectedFieldCellAt(rowIndex, fieldIndex);
    await expect(async () => {
      await cell.click();
      if (await selected.isVisible()) {
        return;
      }
      await cell.locator(".grid-view__cell").click();
      if (!(await selected.isVisible())) {
        throw new Error("Expected field cell to be selected.");
      }
    }).toPass({
      timeout: 5_000,
    });
  }

  /** Single-click the primary cell to select it without entering edit mode */
  async selectPrimaryCell(rowIndex: number): Promise<void> {
    const cell = this.primaryCellAt(rowIndex);
    const selected = this.selectedPrimaryCellAt(rowIndex);
    await expect(async () => {
      await cell.click();
      if (await selected.isVisible()) {
        return;
      }
      await cell.locator(".grid-view__cell").click();
      if (!(await selected.isVisible())) {
        throw new Error("Expected primary cell to be selected.");
      }
    }).toPass({
      timeout: 5_000,
    });
  }

  /**
   * Select a non-primary cell and press Enter to enter edit mode.
   * Waits for the editor input/textarea to appear.
   */
  async startEditingField(rowIndex: number, fieldIndex: number): Promise<void> {
    await this.selectFieldCell(rowIndex, fieldIndex);
    await this.page.keyboard.press("Enter");
    await expect(this.activeEditor()).toBeVisible({ timeout: 10_000 });
  }

  /**
   * Select the primary cell and press Enter to enter edit mode.
   */
  async startEditingPrimary(rowIndex: number): Promise<void> {
    await this.selectPrimaryCell(rowIndex);
    await this.page.keyboard.press("Enter");
    await expect(this.activeEditor()).toBeVisible({ timeout: 10_000 });
  }

  /**
   * Select a rich text cell and press Enter to open its TipTap editor.
   */
  async startEditingRichTextField(
    rowIndex: number,
    fieldIndex: number,
  ): Promise<void> {
    await this.selectFieldCell(rowIndex, fieldIndex);
    await this.page.keyboard.press("Enter");
    await expect(this.activeRichTextEditor()).toBeVisible({ timeout: 10_000 });
  }

  /** Type into the currently active editor (replaces existing content) */
  async type(text: string): Promise<void> {
    await this.activeEditor().fill(text);
  }

  /** Press Enter: saves the value and moves selection to the cell below */
  async confirmWithEnter(): Promise<void> {
    await this.page.keyboard.press("Enter");
  }

  /**
   * Press Tab: saves the value and moves selection to the next cell in the
   * same row, keeping the row selected (the warning remains visible).
   */
  async confirmWithTab(): Promise<void> {
    await this.page.keyboard.press("Tab");
  }

  async selectSingleSelectOption(
    rowIndex: number,
    fieldIndex: number,
    option: string,
  ): Promise<void> {
    await this.selectFieldCell(rowIndex, fieldIndex);
    await this.page.keyboard.press("Enter");

    const optionItem = this.page
      .locator(".select-options__dropdown-item:not(.hidden)", {
        hasText: this.exactTextRegex(option),
      })
      .first();
    await expect(optionItem).toBeVisible({ timeout: 10_000 });
    await optionItem.locator(".select-options__dropdown-link").click();
  }

  /** Press Escape: cancels the edit and reverts to the original value */
  async cancelEdit(): Promise<void> {
    await this.page.keyboard.press("Escape");
  }

  private shortcut(key: string): string {
    return `${process.platform === "darwin" ? "Meta" : "Control"}+${key}`;
  }

  async copyShortcut(): Promise<void> {
    await this.page.keyboard.press(this.shortcut("C"));
  }

  async pasteShortcut(): Promise<void> {
    await this.page.keyboard.press(this.shortcut("V"));
  }

  async writeClipboard(text: string): Promise<void> {
    await this.page
      .context()
      .grantPermissions(["clipboard-read", "clipboard-write"], {
        origin: this.baseUrl,
      });
    await this.page.evaluate(
      (value) => navigator.clipboard.writeText(value),
      text,
    );
  }

  /**
   * Click the grid column header area (RIGHT section) to deselect any
   * selected cell without triggering any row operation. Uses the right
   * section specifically because both sections have a `.grid-view__head`
   * element and strict mode requires a unique match.
   */
  async clickAway(): Promise<void> {
    await this.page
      .locator(".grid-view__right .grid-view__head")
      .click({ position: { x: 5, y: 5 } });
  }

  async renderedRowCount(): Promise<number> {
    return await this.rightRows().count();
  }

  async reduceCurrentBufferToSlice(
    startIndex: number,
    limit: number,
    viewportAlign: "start" | "end" = "start",
  ): Promise<void> {
    await this.page.evaluate(
      async ({ start, rowLimit, align }) => {
        const nuxtWindow = window as unknown as {
          useNuxtApp?: () => { $store: any };
        };
        const store = nuxtWindow.useNuxtApp?.().$store;
        if (!store) {
          throw new Error("Expected Nuxt store to be available.");
        }

        const gridStore = ["page/view/grid", "view/grid"].find((namespace) =>
          Object.prototype.hasOwnProperty.call(
            store.getters,
            `${namespace}/getAllRows`,
          ),
        );
        if (!gridStore) {
          throw new Error("Expected grid Vuex module to be registered.");
        }

        const rows = store.getters[`${gridStore}/getAllRows`];
        if (rows.length < start + rowLimit) {
          throw new Error(
            `Expected at least ${start + rowLimit} buffered rows, got ${
              rows.length
            }.`,
          );
        }

        const rowsInSlice = rows.slice(start, start + rowLimit);
        const count = store.getters[`${gridStore}/getCount`];
        const rowHeight = store.getters[`${gridStore}/getRowHeight`];
        store.commit(`${gridStore}/ADD_ROWS`, {
          rows: [],
          prependToRows: -rows.length,
          appendToRows: 0,
          count,
          bufferStartIndex: start,
          bufferLimit: 0,
        });
        store.commit(`${gridStore}/ADD_ROWS`, {
          rows: rowsInSlice,
          prependToRows: 0,
          appendToRows: rowsInSlice.length,
          count,
          bufferStartIndex: start,
          bufferLimit: rowsInSlice.length,
        });
        if (align === "end") {
          await store.dispatch(
            `${gridStore}/visibleByScrollTop`,
            count * rowHeight,
          );
        } else {
          store.commit(`${gridStore}/SET_ROWS_INDEX`, {
            startIndex: 0,
            endIndex: rowsInSlice.length,
            top: start * rowHeight,
          });
          store.commit(`${gridStore}/SET_SCROLL_TOP`, start * rowHeight);
        }
      },
      { start: startIndex, rowLimit: limit, align: viewportAlign },
    );
  }

  /**
   * Scroll the grid (via real wheel events) until the row whose primary cell
   * contains `text` is rendered and visible. Used to reach a deep row in a large
   * table so the loaded buffer is a genuine window (the top of the table stays
   * unloaded), matching real virtualization.
   */
  async scrollPrimaryIntoView(text: string): Promise<void> {
    const target = this.leftRows().filter({ hasText: text }).first();
    await this.rightRows().first().hover();
    for (let i = 0; i < 100; i += 1) {
      if ((await target.count()) > 0 && (await target.isVisible())) {
        return;
      }
      await this.page.mouse.wheel(0, 1500);
      await this.page.waitForTimeout(80);
    }
    await expect(target).toBeVisible({ timeout: 5_000 });
  }

  /**
   * Right-click a row to open its context menu.
   * We right-click the RIGHT section row (field cell area) because the left
   * section's row-controls area does not reliably trigger the context menu.
   */
  async rightClickRow(rowIndex: number): Promise<void> {
    const row = this.rightRowAt(rowIndex);
    await row.waitFor({ state: "visible", timeout: 10_000 });
    const deleteRow = this.contextItem("Delete row");
    await expect(async () => {
      await row.click({
        button: "right",
        position: { x: 10, y: 10 },
      });
      if (!(await deleteRow.isVisible())) {
        throw new Error("Expected row context menu to open.");
      }
    }).toPass({
      timeout: 5_000,
    });
  }

  contextMenu(): Locator {
    return this.page.locator(".context__menu:visible").first();
  }

  contextItem(label: string): Locator {
    return this.page
      .locator(".context__menu:visible .context__menu-item-link", {
        hasText: label,
      })
      .first();
  }

  async clickContextItem(label: string): Promise<void> {
    await this.contextItem(label).click();
  }

  async openRowModalFromContext(rowIndex: number): Promise<void> {
    await this.rightClickRow(rowIndex);
    await this.clickContextItem("Enlarge row");
    await expect(this.rowEditModal()).toBeVisible({ timeout: 10_000 });
  }

  async closeRowModal(): Promise<void> {
    await this.rowEditModal().locator(".modal__close").click();
    await expect(this.rowEditModal()).toHaveCount(0, { timeout: 10_000 });
  }

  /**
   * Fill a text field inside the open row edit modal and blur it so the value
   * is persisted.
   */
  async fillRowModalTextField(fieldName: string, value: string): Promise<void> {
    const input = this.rowEditModalTextField(fieldName);
    await input.fill(value);
    await input.blur();
  }

  private escapeRegex(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  private exactTextRegex(value: string): RegExp {
    return new RegExp(`^\\s*${this.escapeRegex(value)}\\s*$`);
  }

  private fieldVisibilityLink(): Locator {
    return this.page
      .locator(".header__filter-link", {
        has: this.page.locator(".header__filter-icon.iconoir-eye-off"),
      })
      .first();
  }

  private fieldVisibilityContext(): Locator {
    return this.page.locator(".hidings:visible").first();
  }

  private fieldVisibilitySwitch(fieldName: string): Locator {
    const context = this.fieldVisibilityContext();

    return context
      .locator(".hidings__item", {
        hasText: new RegExp(`\\b${this.escapeRegex(fieldName)}\\b`),
      })
      .locator(".switch")
      .first();
  }

  async openFieldVisibilityContext(): Promise<void> {
    await expect(this.fieldVisibilityLink()).toBeVisible({ timeout: 10_000 });
    await this.fieldVisibilityLink().click();
    await expect(this.fieldVisibilityContext()).toBeVisible({
      timeout: 10_000,
    });
  }

  async setFieldVisibility(fieldName: string, visible: boolean): Promise<void> {
    const fieldSwitch = this.fieldVisibilitySwitch(fieldName);
    await expect(fieldSwitch).toBeVisible({ timeout: 10_000 });

    const isVisible = await fieldSwitch.evaluate((element) =>
      element.classList.contains("switch--active"),
    );
    if (isVisible !== visible) {
      await fieldSwitch.click();
    }

    if (visible) {
      await expect(fieldSwitch).toHaveClass(/switch--active/, {
        timeout: 10_000,
      });
    } else {
      await expect(fieldSwitch).not.toHaveClass(/switch--active/, {
        timeout: 10_000,
      });
    }
  }

  private rowIdentifierDropdownIcon(): Locator {
    return this.page.locator(
      ".grid-view__left .grid-view__head-row-identifier-dropdown",
    );
  }

  async selectRowIdentifierType(type: "id" | "count"): Promise<void> {
    await this.rowIdentifierDropdownIcon().click();
    const label = type === "id" ? "Row identifier" : "Count";
    await this.page
      .locator(".select__item-link", {
        hasText: new RegExp(`^\\s*${label}\\s*$`),
      })
      .first()
      .click();
  }

  rowIdentifierContentAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__row-count-content");
  }

  rowCountWrapperAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__row-count");
  }

  rowDragHandleAt(rowIndex: number): Locator {
    return this.leftRowAt(rowIndex).locator(".grid-view__row-drag");
  }

  async hoverRow(rowIndex: number): Promise<void> {
    await this.leftRowAt(rowIndex).hover();
  }

  async unhoverRow(): Promise<void> {
    await this.page
      .locator(".grid-view__left .grid-view__head")
      .hover({ position: { x: 5, y: 5 } });
  }

  private rowHeightLink(): Locator {
    return this.page
      .locator(".header__filter-link", {
        has: this.page.locator(".header__filter-icon.iconoir-table-rows"),
      })
      .first();
  }

  async selectRowHeight(label: "Small" | "Medium" | "Large"): Promise<void> {
    await expect(this.rowHeightLink()).toBeVisible({ timeout: 10_000 });
    await this.rowHeightLink().click();

    const item = this.page
      .locator(".select__items:visible .select__item", {
        hasText: new RegExp(`^\\s*${label}\\s*$`),
      })
      .first();
    await expect(item).toBeVisible({ timeout: 10_000 });
    await item.locator(".select__item-link").click();
  }

  // -- Assertions --------------------------------------------------------------

  /** Assert that exactly `count` rows are visible in the right section */
  async expectRowCount(count: number): Promise<void> {
    await expect(this.rightRows()).toHaveCount(count, { timeout: 10_000 });
  }

  async expectRowNotLoading(rowIndex: number): Promise<void> {
    await expect(this.leftRowAt(rowIndex)).not.toHaveClass(
      /grid-view__row--loading/,
      { timeout: 10_000 },
    );
    await expect(this.rightRowAt(rowIndex)).not.toHaveClass(
      /grid-view__row--loading/,
      { timeout: 10_000 },
    );
  }

  async expectRowLoading(rowIndex: number): Promise<void> {
    // The visible spinner is rendered in the left row-details cell via the row
    // count, so the left row is the stable user-visible loading signal.
    await expect(this.leftRowAt(rowIndex)).toHaveClass(
      /grid-view__row--loading/,
      { timeout: 10_000 },
    );
  }

  async expectNoRowsLoading(): Promise<void> {
    await expect(this.page.locator(".grid-view__row--loading")).toHaveCount(0, {
      timeout: 10_000,
    });
  }

  /**
   * Assert the visible text of the primary field cell at `rowIndex`.
   * Searches the LEFT section.
   */
  async expectPrimaryText(rowIndex: number, text: string): Promise<void> {
    await expect(this.primaryCellAt(rowIndex)).toHaveText(
      this.exactTextRegex(text),
      {
        timeout: 10_000,
      },
    );
  }

  async expectFieldText(
    rowIndex: number,
    fieldIndex: number,
    text: string,
  ): Promise<void> {
    await expect(this.fieldCellAt(rowIndex, fieldIndex)).toHaveText(
      this.exactTextRegex(text),
      {
        timeout: 10_000,
      },
    );
  }

  async expectSingleSelectFieldText(
    rowIndex: number,
    fieldIndex: number,
    text: string,
  ): Promise<void> {
    await expect(this.singleSelectOptionAt(rowIndex, fieldIndex)).toHaveText(
      this.exactTextRegex(text),
      {
        timeout: 10_000,
      },
    );
  }

  async expectPrimaryEmpty(rowIndex: number): Promise<void> {
    await expect(this.primaryCellAt(rowIndex)).toBeEmpty({
      timeout: 10_000,
    });
  }

  /**
   * Assert that the LEFT section contains a row whose primary field text
   * includes `text`. Use this to check existence, not for interaction.
   */
  async expectPrimaryVisible(text: string): Promise<void> {
    await expect(this.leftRows().filter({ hasText: text })).toBeVisible({
      timeout: 10_000,
    });
  }

  async expectPrimaryNotVisible(text: string): Promise<void> {
    await expect(this.leftRows().filter({ hasText: text })).not.toBeVisible({
      timeout: 10_000,
    });
  }

  async expectFieldEmpty(rowIndex: number, fieldIndex: number): Promise<void> {
    await expect(this.fieldCellAt(rowIndex, fieldIndex)).toBeEmpty({
      timeout: 5_000,
    });
  }

  async expectNonPrimaryFieldHeaderVisible(fieldName: string): Promise<void> {
    await expect(
      this.nonPrimaryFieldHeadersByName(fieldName).first(),
    ).toBeVisible({
      timeout: 10_000,
    });
  }

  async expectNonPrimaryFieldHeaderHidden(fieldName: string): Promise<void> {
    await expect(this.nonPrimaryFieldHeadersByName(fieldName)).toHaveCount(0, {
      timeout: 10_000,
    });
  }

  async expectFrozenFieldHeaderVisible(fieldName: string): Promise<void> {
    await expect(this.frozenFieldHeadersByName(fieldName).first()).toBeVisible({
      timeout: 10_000,
    });
  }

  async expectScrollableFieldHeaderHidden(fieldName: string): Promise<void> {
    await expect(this.nonPrimaryFieldHeadersByName(fieldName)).toHaveCount(0, {
      timeout: 10_000,
    });
  }

  async expectVisibleNonPrimaryFieldCount(count: number): Promise<void> {
    await expect(
      this.page.locator(
        ".grid-view__right .grid-view__head .grid-view__description-name",
      ),
    ).toHaveCount(count, { timeout: 10_000 });
    await expect(this.rightRowAt(0).locator(".grid-view__column")).toHaveCount(
      count,
      { timeout: 10_000 },
    );
  }

  async expectPrimarySelected(rowIndex: number): Promise<void> {
    await expect(this.selectedPrimaryCellAt(rowIndex)).toBeVisible({
      timeout: 5_000,
    });
  }

  async expectFieldSelected(
    rowIndex: number,
    fieldIndex: number,
  ): Promise<void> {
    await expect(this.selectedFieldCellAt(rowIndex, fieldIndex)).toBeVisible({
      timeout: 5_000,
    });
  }

  async expectActiveCellError(text: string): Promise<void> {
    await expect(this.activeCellError()).toContainText(text, {
      timeout: 10_000,
    });
  }

  async expectActiveEditorValue(value: string): Promise<void> {
    await expect(this.activeEditor()).toHaveValue(value, { timeout: 5_000 });
  }

  async expectMultiSelectedCellCount(count: number): Promise<void> {
    await expect(this.multiSelectedCells()).toHaveCount(count, {
      timeout: 5_000,
    });
  }

  async expectRowCheckboxChecked(rowIndex: number): Promise<void> {
    await expect(this.checkboxNativeAt(rowIndex)).toBeChecked({
      timeout: 5_000,
    });
  }

  async expectRowModalVisibleFor(primaryValue: string): Promise<void> {
    await expect(this.rowEditModal()).toBeVisible({ timeout: 10_000 });
    await expect(this.rowEditModal()).toContainText(primaryValue, {
      timeout: 10_000,
    });
  }

  async expectRowModalTextFieldValue(
    fieldName: string,
    value: string,
  ): Promise<void> {
    await expect(this.rowEditModalTextField(fieldName)).toHaveValue(value, {
      timeout: 10_000,
    });
  }

  async expectGroupByBanner(
    value: string,
    count: number,
    collapsed = false,
  ): Promise<void> {
    const banner = this.groupByBannerByValue(value);
    await expect(banner).toBeVisible({ timeout: 10_000 });
    await expect(
      banner.locator(".grid-view__group-by-banner-value"),
    ).toHaveText(new RegExp(`^\\s*${this.escapeRegex(value)}\\s*$`), {
      timeout: 10_000,
    });
    await expect(
      banner.locator(".grid-view__group-by-banner-count"),
    ).toHaveText(new RegExp(`^\\s*${count}\\s*$`), { timeout: 10_000 });
    await expect(banner).toHaveAttribute(
      "data-collapsed",
      collapsed ? "true" : "false",
      { timeout: 10_000 },
    );
  }

  async expectNoGroupByBanner(value: string): Promise<void> {
    await expect(this.groupByBannerByValue(value)).toHaveCount(0, {
      timeout: 10_000,
    });
  }

  /**
   * Assert a group-by header aggregation value is shown `count` times. The text is
   * the short name + value concatenated, e.g. "Sum30"; whitespace is ignored. Polls,
   * so it also covers the live in-place update after an edit.
   */
  async expectGroupAggregation(text: string, count = 1): Promise<void> {
    const want = text.replace(/\s+/g, "");
    await expect(async () => {
      const texts = await this.page
        .locator(".grid-view__group-by-banner-aggregation")
        .allTextContents();
      const matches = texts.filter(
        (t) => t.replace(/\s+/g, "") === want,
      ).length;
      expect(matches).toBe(count);
    }).toPass({ timeout: 10_000 });
  }

  /** Assert the bottom footer shows an aggregation value, e.g. "Sum35". */
  async expectFooterAggregation(text: string): Promise<void> {
    const want = text.replace(/\s+/g, "");
    await expect(async () => {
      const texts = await this.page
        .locator(".grid-view__foot .grid-view-aggregation")
        .allTextContents();
      expect(texts.map((t) => t.replace(/\s+/g, ""))).toContain(want);
    }).toPass({ timeout: 10_000 });
  }

  /**
   * Assert that the row at `rowIndex` has the warning class
   * (shown when matchFilters, matchSortings, or matchSearch is false
   * while the row is still selected).
   */
  async expectRowHasWarning(rowIndex: number): Promise<void> {
    await expect(this.leftRowAt(rowIndex)).toHaveClass(
      /grid-view__row--warning/,
      { timeout: 10_000 },
    );
  }

  async expectRowWarningVisible(rowIndex: number): Promise<void> {
    await expect(this.rowWarningAt(rowIndex)).toBeVisible({
      timeout: 10_000,
    });
  }

  async expectRowWarningText(rowIndex: number, text: string): Promise<void> {
    await expect(this.rowWarningAt(rowIndex)).toContainText(text, {
      timeout: 10_000,
    });
  }

  /**
   * The last row in the LEFT section. Unlike a snapshotted `renderedRowCount() - 1`
   * index, this re-resolves on every poll, so assertions stay correct even if a
   * re-render changes the row count mid-assertion.
   */
  lastLeftRow(): Locator {
    return this.leftRows().last();
  }

  async expectLastRowPrimaryEmpty(): Promise<void> {
    await expect(
      this.lastLeftRow().locator(".grid-view__column").last(),
    ).toBeEmpty({ timeout: 10_000 });
  }

  async expectLastRowLoading(): Promise<void> {
    await expect(this.lastLeftRow()).toHaveClass(/grid-view__row--loading/, {
      timeout: 10_000,
    });
  }

  async expectLastRowWarning(text: string): Promise<void> {
    await expect(this.lastLeftRow()).toHaveClass(/grid-view__row--warning/, {
      timeout: 10_000,
    });
    await expect(
      this.lastLeftRow().locator(".grid-view__row-warning"),
    ).toContainText(text, { timeout: 10_000 });
  }

  async expectLastRowPrimaryText(text: string): Promise<void> {
    await expect(
      this.lastLeftRow().locator(".grid-view__column").last(),
    ).toHaveText(this.exactTextRegex(text), { timeout: 10_000 });
  }

  async expectLastRowNoWarning(): Promise<void> {
    await expect(this.lastLeftRow()).not.toHaveClass(
      /grid-view__row--warning/,
      { timeout: 10_000 },
    );
  }

  async expectPrimaryRowHasWarning(
    primaryText: string,
    warningText: string,
  ): Promise<void> {
    const row = this.leftRows().filter({ hasText: primaryText });
    await expect(row).toHaveClass(/grid-view__row--warning/, {
      timeout: 10_000,
    });
    await expect(row.locator(".grid-view__row-warning")).toContainText(
      warningText,
      { timeout: 10_000 },
    );
  }

  async expectRowNoWarning(rowIndex: number): Promise<void> {
    await expect(this.leftRowAt(rowIndex)).not.toHaveClass(
      /grid-view__row--warning/,
      { timeout: 10_000 },
    );
  }

  /** Assert that the nth cell (right section) has the search-match highlight */
  async expectCellHighlighted(
    rowIndex: number,
    fieldIndex: number,
  ): Promise<void> {
    await expect(this.fieldCellAt(rowIndex, fieldIndex)).toHaveClass(
      /grid-view__column--matches-search/,
      { timeout: 10_000 },
    );
  }

  async expectCellNotHighlighted(
    rowIndex: number,
    fieldIndex: number,
  ): Promise<void> {
    await expect(this.fieldCellAt(rowIndex, fieldIndex)).not.toHaveClass(
      /grid-view__column--matches-search/,
      { timeout: 10_000 },
    );
  }

  /** Assert that the primary (Name) cell at rowIndex has the search-match highlight */
  async expectPrimaryHighlighted(rowIndex: number): Promise<void> {
    await expect(this.primaryCellAt(rowIndex)).toHaveClass(
      /grid-view__column--matches-search/,
      { timeout: 10_000 },
    );
  }

  async expectPrimaryNotHighlighted(rowIndex: number): Promise<void> {
    await expect(this.primaryCellAt(rowIndex)).not.toHaveClass(
      /grid-view__column--matches-search/,
      { timeout: 10_000 },
    );
  }

  async expectRowHeight(
    size: "small" | "medium" | "large",
    expectedPx: number,
    rowIndex = 0,
  ): Promise<void> {
    await expect(this.gridRoot()).toHaveClass(
      new RegExp(`grid-view--row-height-${size}`),
      { timeout: 10_000 },
    );
    await expect(this.leftRowAt(rowIndex)).toHaveCSS(
      "height",
      `${expectedPx}px`,
      { timeout: 10_000 },
    );
    await expect(this.rightRowAt(rowIndex)).toHaveCSS(
      "height",
      `${expectedPx}px`,
      { timeout: 10_000 },
    );
  }

  async expectRowIdentifierText(rowIndex: number, text: string): Promise<void> {
    await this.page.mouse.move(0, 0);
    await expect(this.rowIdentifierContentAt(rowIndex)).toHaveText(text, {
      timeout: 10_000,
    });
  }

  async expectRowCountVisible(rowIndex: number): Promise<void> {
    await expect(this.rowCountWrapperAt(rowIndex)).toBeVisible({
      timeout: 5_000,
    });
  }

  async expectRowCountHidden(rowIndex: number): Promise<void> {
    await expect(this.rowCountWrapperAt(rowIndex)).not.toBeVisible({
      timeout: 5_000,
    });
  }

  async expectRowCheckboxVisible(rowIndex: number): Promise<void> {
    await expect(this.checkboxAt(rowIndex)).toBeVisible({ timeout: 5_000 });
  }

  async expectRowCheckboxHidden(rowIndex: number): Promise<void> {
    await expect(this.checkboxAt(rowIndex)).not.toBeVisible({ timeout: 5_000 });
  }

  async expectRowDragHandlePresent(rowIndex: number): Promise<void> {
    await expect(this.rowDragHandleAt(rowIndex)).toHaveCount(1, {
      timeout: 10_000,
    });
  }

  async expectRowDragHandleAbsent(rowIndex: number): Promise<void> {
    await expect(this.rowDragHandleAt(rowIndex)).toHaveCount(0, {
      timeout: 10_000,
    });
  }

  async expectRowBackgroundColor(
    rowIndex: number,
    color: string,
  ): Promise<void> {
    const colorClass = new RegExp(
      `background-color--${this.escapeRegex(color)}`,
    );
    await expect(
      this.page
        .locator(".grid-view__left .grid-view__row-background-wrapper")
        .nth(rowIndex),
    ).toHaveClass(colorClass, { timeout: 10_000 });
    await expect(
      this.page
        .locator(".grid-view__right .grid-view__row-background-wrapper")
        .nth(rowIndex),
    ).toHaveClass(colorClass, { timeout: 10_000 });
  }

  /**
   * Assert the decoration color actually paints: the row element stacked on top
   * of the colored `.grid-view__row-background-wrapper` must keep a transparent
   * background in both grid sections, otherwise the wrapper color is hidden
   * even though the color class is applied.
   */
  async expectRowBackgroundNotObscured(rowIndex: number): Promise<void> {
    const transparent = "rgba(0, 0, 0, 0)";
    await expect(
      this.page
        .locator(
          ".grid-view__left .grid-view__row-background-wrapper > .grid-view__row",
        )
        .nth(rowIndex),
    ).toHaveCSS("background-color", transparent, { timeout: 10_000 });
    await expect(
      this.page
        .locator(
          ".grid-view__right .grid-view__row-background-wrapper > .grid-view__row",
        )
        .nth(rowIndex),
    ).toHaveCSS("background-color", transparent, { timeout: 10_000 });
  }

  /**
   * Assert that an error toast is visible.
   *
   * Baserow toasts render as:
   *   <div class="toast">
   *     <div class="toast__icon toast__icon--error">...</div>
   *   </div>
   *
   * The type modifier is on the icon child, not the root element, so we
   * target `.toast__icon--error` rather than a non-existent `.toast--error`.
   */
  async expectErrorToast(): Promise<void> {
    await expect(this.page.locator(".toast__icon--error").first()).toBeVisible({
      timeout: 10_000,
    });
  }
}
