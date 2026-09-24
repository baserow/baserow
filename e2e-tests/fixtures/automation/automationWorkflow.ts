import { getClient } from "../../client"
import { waitForJob } from "../job"
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

/**
 * Publishes a workflow and waits for the publish job to finish, so a button
 * or a test run can start it the moment this returns.
 */
export async function publishAutomationWorkflow(
  workflow: AutomationWorkflow,
): Promise<void> {
  const client = getClient(workflow.automation.workspace.user);
  const job: any = await client.post(
    `automation/workflows/${workflow.id}/publish/async/`,
    {},
  );
  await waitForJob(client, job.data.id, `Publishing "${workflow.name}"`);
}
