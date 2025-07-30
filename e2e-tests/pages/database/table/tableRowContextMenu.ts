import { Locator, Page } from "@playwright/test";
import { BaserowPage } from "../../baserowPage";


export class TableRowContextMenuPage extends BaserowPage {
  private readonly deleteRowButton: Locator;

  constructor(page: Page) {
    super(page);
    this.deleteRowButton = this.page.getByText('Delete row', { exact: true }).describe('Delete row')
  }

  async deleteRow() {
    await this.deleteRowButton.click()
  }
}
