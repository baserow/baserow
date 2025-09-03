import { BaserowPage } from "../../baserowPage";

export class TableHeaderPage extends BaserowPage {
  async toggleFiltersPanel() {
    await this.page.locator('a.header__filter-link').filter({ hasText: 'Filter' }).click()
  }
}
