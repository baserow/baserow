import { Locator, Page } from "@playwright/test";
import { BaserowPage } from "../../baserowPage";

export class FieldContextFormPage extends BaserowPage {
  private readonly fieldContextForm: Locator;

  constructor(page: Page) {
    super(page);
    this.fieldContextForm = this.page.locator('.field-context')
  }

  async fillName(name: string) {
    await this.fieldContextForm.getByPlaceholder('Name').first().fill(name);
  }

  async fillDefaultText(text: string) {
    await this.fieldContextForm.getByPlaceholder('Default text').fill(text);
  }

  async focusFieldType() {
    this.fieldContextForm.getByTestId('fieldTypesDropdown').locator('a.dropdown__selected').first().click()
  }

  async selectFieldType(fieldType: string) {
    await this.fieldContextForm.getByTestId('fieldTypesDropdown').locator('a').filter({ hasText: fieldType }).first().click();
  }

  async create() {
    await this.fieldContextForm.locator('button').filter({ hasText: 'Create' }).click()
  }

  async save() {
    await this.fieldContextForm.locator('button').filter({ hasText: 'Save' }).click()
  }
}
