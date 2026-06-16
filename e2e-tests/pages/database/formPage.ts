import { expect, Locator } from "@playwright/test";
import { BaserowPage, PageConfig } from "../baserowPage";

/**
 * Drives the public form page (`/form/{slug}`): field visibility, link-row
 * dropdown selection, submitting, and reading back the submitted state.
 */
export class FormPage extends BaserowPage {
  private readonly submitButton: Locator;
  private readonly submittedMessage: Locator;
  private readonly openDropdownItems: Locator;

  constructor(pageConfig: PageConfig) {
    super(pageConfig);
    this.submitButton = this.page.locator(".form-view__body button.button");
    this.submittedMessage = this.page.locator(".form-view__submitted");
    // The items container of whichever dropdown is currently open.
    this.openDropdownItems = this.page.locator(".dropdown__items:not(.hidden)");
  }

  async gotoPublic(slug: string) {
    this.pageUrl = `form/${slug}`;
    await this.goto();
  }

  /**
   * Wrapper of the field whose label contains `name`. Matching is by substring
   * because required fields append a "*", so avoid names that are prefixes of
   * one another.
   */
  fieldWrapper(name: string): Locator {
    return this.page.locator(".form-view__field-wrapper").filter({
      has: this.page.locator(".form-view__field-name", { hasText: name }),
    });
  }

  async isFieldVisible(name: string): Promise<boolean> {
    return (await this.fieldWrapper(name).count()) > 0;
  }

  async openLinkDropdown(fieldName: string) {
    await this.fieldWrapper(fieldName).locator(".dropdown__selected").click();
    await expect(this.openDropdownItems).toBeVisible();
    // Options are fetched on open; wait for the list to settle before clicking.
    await expect(
      this.openDropdownItems.locator(".select__items-loading"),
    ).toHaveCount(0);
  }

  dropdownOption(text: string): Locator {
    return this.openDropdownItems
      .locator(".select__item-name")
      .filter({ hasText: text });
  }

  async pickLinkOption(fieldName: string, text: string) {
    await this.openLinkDropdown(fieldName);
    const option = this.dropdownOption(text);
    await option.waitFor({ state: "visible" });
    await option.click();
  }

  async submit() {
    await this.submitButton.click();
  }

  async expectSubmitted() {
    await expect(this.submittedMessage).toBeVisible();
  }

  async expectNotSubmitted() {
    await expect(this.submittedMessage).toBeHidden();
  }

  /**
   * Records calls to the form submit endpoint. Returns a getter for the count,
   * so a test can assert client-side validation blocked the request instead of
   * the backend rejecting it.
   */
  trackSubmitRequests(): () => number {
    let count = 0;
    this.page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/submit/")) {
        count += 1;
      }
    });
    return () => count;
  }

  requiredError(fieldName: string): Locator {
    return this.fieldWrapper(fieldName).locator(".control__messages--error");
  }
}
