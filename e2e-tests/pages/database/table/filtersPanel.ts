import { Locator, Page } from "@playwright/test";
import { BaserowPage } from "../../baserowPage";

export class FiltersPanelPage extends BaserowPage {
  readonly filtersPanel: Locator;

  constructor(page: Page) {
    super(page);
    this.filtersPanel = this.page.locator('.filters__content').describe('Filters panel')
  }

  async addFilter() {
    await this.filtersPanel.getByRole('button', { name: 'Add filter', exact: true }).click()
  }

  getFilterRow(index: number) {
    return this.filtersPanel.locator('.filters__item-wrapper').nth(index)
  }
}

export class FiltersPanelRowPage extends BaserowPage {
  readonly filterRow: Locator;

  constructor(page: Page, filterRow: Locator) {
    super(page);
    this.filterRow = filterRow
  }

  async delete() {
    await this.filterRow.locator('a.filters__remove').click()
  }
}

