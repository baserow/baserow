import { Page } from "@playwright/test"
import { BaserowPage } from "../baserowPage"
import { Automation } from "../../fixtures/automation/automation"
import { AutomationWorkflow } from "../../fixtures/automation/automationWorkflow"
import { Workspace } from "../../fixtures/workspace"


export class AutomationWorkflowPage extends BaserowPage {
  automationWorkflow: AutomationWorkflow
  automation: Automation
  readonly workspace: Workspace

  constructor(page: Page, automation: Automation, automationWorkflow: AutomationWorkflow) {
    super(page)
    this.automation = automation
    this.automationWorkflow = automationWorkflow
  }

  async removeAll() {}

  getFullUrl() {
    return `${this.baseUrl}/automation/${this.automation.id}/workflow/${this.automationWorkflow.id}`;
  }
}
