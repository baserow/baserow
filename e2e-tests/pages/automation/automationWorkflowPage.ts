import { BaserowPage, PageConfig } from "../baserowPage";
import { Automation } from "../../fixtures/automation/automation";
import { AutomationWorkflow } from "../../fixtures/automation/automationWorkflow";
import { Workspace } from "../../fixtures/workspace";

export class AutomationWorkflowPage extends BaserowPage {
  automationWorkflow: AutomationWorkflow;
  automation: Automation;
  readonly workspace: Workspace;

  constructor(
    pageConfig: PageConfig,
    automation: Automation,
    automationWorkflow: AutomationWorkflow
  ) {
    super(pageConfig);
    this.automation = automation;
    this.automationWorkflow = automationWorkflow;
  }

  async removeAll() {}

  /**
   * Fully reloads workflow pages so API-created workflow/node fixtures are read
   * from the backend before the graph-backed canvas is asserted.
   */
  async goto() {
    await this.page.waitForTimeout(100);
    await this.page.goto(this.getFullUrl(), { waitUntil: "load" });
    await this.recoverFromNuxtError();
  }

  getFullUrl() {
    return `${this.baseUrl}/automation/${this.automation.id}/workflow/${this.automationWorkflow.id}`;
  }
}
