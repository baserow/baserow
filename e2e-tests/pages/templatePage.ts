import { Page } from "@playwright/test";
import { BaserowPage } from "./baserowPage";

export class TemplatePage extends BaserowPage {
  readonly templateSlug: String;

  constructor(page: Page, slug: String) {
    super(page);
    this.templateSlug = slug;
  }

  getFullUrl() {
    return `${this.baseUrl}/template/${this.templateSlug}`;
  }
}
