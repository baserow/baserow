import { BaserowPage } from "../../baserowPage";

export class FieldContextMenuPage extends BaserowPage {
  async edit() {
    await this.page.getByText('Edit field', { exact: true }).click()
  }

  async hide() {
    await this.page.getByText('Hide field', { exact: true }).click()
  }

  async delete() {
    await this.page.getByText('Delete field', { exact: true }).click()
  }
}
