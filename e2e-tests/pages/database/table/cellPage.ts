import { Locator, Page } from "@playwright/test";
import { BaserowPage } from "../../baserowPage";

export class CellPage extends BaserowPage {
  protected cell: Locator;
  protected cellInput: Locator;

  async getValue() {
    return await this.cell.innerText()
  }
}

export class TextCellPage extends CellPage {
  constructor(page: Page, cell: Locator) {
    super(page);
    this.cell = cell.locator('.grid-field-text').first().describe("Text cell");
    this.cellInput = cell.locator('.grid-field-text__input').first().describe("Text cell input");
  }

  async fill(text: string) {
    await this.cell.dblclick();
    await this.cellInput.fill(text);
    await this.cellInput.press('Enter')
  }
}

export class NumberCellPage extends CellPage {
  constructor(page: Page, cell: Locator) {
    super(page);
    this.cell = cell.locator('.grid-field-number').first().describe("Number cell");
  }
}
