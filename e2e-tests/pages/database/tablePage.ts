import { expect, Locator, Page } from "@playwright/test";
import { BaserowPage } from "../baserowPage";
import { Table } from "../../fixtures/database/table";

const TEST_IMAGE_FILE_PATH = "assets/testuploadimage.png";

export class TablePage extends BaserowPage {
  private readonly projectsTextLocator: Locator;
  private readonly addColumnLocator: Locator;
  private readonly createButtonLocator: Locator;
  private readonly firstFileCellLocator: Locator;
  private readonly addFileLocator: Locator;
  private readonly fileZoneLocator: Locator;
  private readonly uploadButtonLocator: Locator;
  private readonly fileCellImageLocator: Locator;
  private readonly searchButtonIcon: Locator;
  private readonly firstNonPrimaryCell: Locator;
  private readonly nonPrimaryRows: Locator;
  readonly firstNonPrimaryCellWrappingColumnDiv: Locator;
  private readonly searchMatchCells: Locator;
  private readonly hideNotMatchingRowsSearchToggle;
  private readonly fieldHeader: Locator;
  private readonly loadingOverlay: Locator;
  private readonly searchInput: Locator;
  readonly rowIdDivsMatchingSearch: Locator;
  readonly firstRowIdDiv: Locator;

  constructor(page: Page) {
    super(page);
    this.projectsTextLocator = this.page.locator("text=Projects");
    this.addColumnLocator = this.page.locator(".grid-view__add-column");
    this.searchButtonIcon = this.page.locator(".header__search-icon");
    this.hideNotMatchingRowsSearchToggle = this.page.getByText(
      "hide not matching rows"
    );
    this.createButtonLocator = this.page.getByRole("button", {
      name: /create/i,
    });
    this.firstFileCellLocator = this.page
      .locator(".grid-field-file__cell")
      .first();
    this.addFileLocator = this.page.locator(".grid-field-file__item-add");
    this.fileZoneLocator = this.page.locator(".upload-files__dropzone");
    this.uploadButtonLocator = this.page
      .locator("button span")
      .filter({ hasText: "Upload" });
    this.fileCellImageLocator = this.page.locator(".grid-field-file__image");
    this.firstNonPrimaryCell = this.page
      .locator(".grid-view__right .grid-view__cell")
      .first();
    this.nonPrimaryRows = this.page.locator(
      ".grid-view__right .grid-view__rows .grid-view__row"
    );
    this.firstNonPrimaryCellWrappingColumnDiv = this.page
      .locator(".grid-view__right .grid-view__rows .grid-view__column")
      .first();
    this.searchMatchCells = this.page.locator(
      ".grid-view__column--matches-search"
    );
    this.fieldHeader = this.page.locator(".grid-view__description");
    this.loadingOverlay = this.page.locator(".content .loading-overlay");
    this.searchInput = this.page.getByPlaceholder("Search in all rows");
    this.rowIdDivsMatchingSearch = this.page.locator(
      ".grid-view__row-info.grid-view__row-info--matches-search"
    );
    this.firstRowIdDiv = this.page.locator(".grid-view__row-info").first();
  }

  async addNewFieldOfType(type: string) {
    await this.addColumnLocator.click();
    await this.page.locator(`.select__item-name-text[title="${type}"]`).click();
    await this.createButtonLocator.click();
  }

  async uploadImageToFirstFileFieldCellAndGetWidth() {
    await this.selectFirstFileCell();
    await this.clickAddFile();
    await this.uploadFile(TEST_IMAGE_FILE_PATH);
    return await this.getWidthOfFirstFileFieldCellImage();
  }
  async selectFirstFileCell() {
    await this.firstFileCellLocator.click();
  }

  async clickAddFile() {
    await this.addFileLocator.click();
  }

  async clickFileZone() {
    const clickFileZonePromise = this.fileZoneLocator.click();
    const fileChooserPromise = this.page.waitForEvent("filechooser");
    const [fileChooser] = await Promise.all([
      fileChooserPromise,
      clickFileZonePromise,
    ]);
    return fileChooser;
  }

  async uploadFile(filePath) {
    const fileChooser = await this.clickFileZone();
    await fileChooser.setFiles(filePath);
    await this.uploadButtonLocator.click();
  }

  async waitForFileFieldCellImage() {
    await this.fileCellImageLocator.waitFor();
  }

  async getWidthOfFirstFileFieldCellImage() {
    await this.waitForFileFieldCellImage();
    return await this.page.evaluate(() => {
      const element = document.querySelector(".grid-field-file__image");
      return element.clientWidth;
    });
  }

  async goToTable(table: Table) {
    this.pageUrl = `database/${table.database.id}/table/${table.id}`;
    await this.goto();
  }

  async clearSearchInput() {
    await this.searchInput.click();
    await this.page.keyboard.press("Control+A");
    await this.page.keyboard.press("Backspace");
    await this.waitForLoadingOverlayToDisappear();
  }

  async openSearchContextAndSearchFor(searchTerm) {
    await this.searchButtonIcon.click();
    await this.searchInput.click();
    await this.page.keyboard.press("Control+A");
    await this.page.keyboard.press("Backspace");
    await this.page.keyboard.type(searchTerm.toString());
    await this.page.keyboard.press("Enter");
    await this.waitForLoadingOverlayToDisappear();
    await this.searchButtonIcon.click();
  }

  async openAndClickSearchToggle(clearInput = false) {
    await this.searchButtonIcon.click();
    if (clearInput) {
      await this.clearSearchInput();
    }
    await this.hideNotMatchingRowsSearchToggle.click();
    await this.waitForLoadingOverlayToDisappear();
    await this.searchButtonIcon.click();
  }

  async inFirstNonPrimaryCellInput(cellValue: string) {
    await this.firstNonPrimaryCell.click();
    await this.page.keyboard.type(cellValue);
    await this.page.keyboard.press("Enter");
  }

  async expectIsSearchHighlighted(locator) {
    await expect(locator).toHaveClass(/.*matches-search.*/);
  }

  async expectIsNotSearchHighlighted(locator) {
    await expect(locator).not.toHaveClass(/.*matches-search.*/);
  }

  rows() {
    return this.nonPrimaryRows;
  }

  searchMatchingCells() {
    return this.searchMatchCells;
  }

  fields() {
    return this.fieldHeader;
  }

  async waitForLoadingOverlayToDisappear() {
    await expect(this.loadingOverlay).toHaveCount(0);
  }

  async waitForFirstCellNotBeBlank() {
    await this.page.evaluate(() => {
      return new Promise((resolve) => {
        setTimeout(resolve, 1000); // Sleep for 1000 milliseconds (1 second)
      });
    });
    await expect(this.firstNonPrimaryCell.locator("*")).not.toHaveCount(0);
  }

  async waitForFirstCellToBeBlank() {
    await expect(this.firstNonPrimaryCell.locator("div *")).toHaveCount(0);
  }
}
