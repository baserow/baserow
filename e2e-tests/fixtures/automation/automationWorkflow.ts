import { getClient } from "../../client"
import { Automation } from "./automation"

export class AutomationWorkflow {
  constructor(
    public id: number,
    public name: string,
    public automation: Automation
  ) {}
}

export async function createAutomationWorkflow(
  workflowName: string,
  automation: Automation,
): Promise<AutomationWorkflow> {
  const response: any = await getClient(automation.workspace.user).post(
    `automation/${automation.id}/workflows/`,
    {
      name: workflowName,
    }
  )
  return new AutomationWorkflow(
    response.data.id,
    response.data.name,
    automation,
  )
}
