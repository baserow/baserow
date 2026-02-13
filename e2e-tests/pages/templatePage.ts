import { Page } from "@playwright/test";
import { BaserowPage, PageConfig } from "./baserowPage";

export class TemplatePage extends BaserowPage {
  readonly templateSlug: String;

  constructor(pageConfig: PageConfig, slug: String) {
    super(pageConfig);
    this.templateSlug = slug;
  }

  getFullUrl() {
    return `${this.baseUrl}/template/${this.templateSlug}`;
  }
}
