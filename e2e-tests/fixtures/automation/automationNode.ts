import { getClient } from "../../client";
import { AutomationWorkflow } from "./automationWorkflow";

export class AutomationNode {
  constructor(
    public id: number,
    public type: string,
    public workflow: AutomationWorkflow
  ) {}
}

export async function createAutomationNode(
  workflow: AutomationWorkflow,
  nodeType: string,
  referenceNodeId: number | null = null,
  position: string = "south",
  output: string = ""
): Promise<AutomationNode> {
  const response: any = await getClient(
    workflow.automation.workspace.user
  ).post(`automation/workflow/${workflow.id}/nodes/`, {
    type: nodeType,
    reference_node_id: referenceNodeId,
    position,
    output,
  });
  return new AutomationNode(response.data.id, nodeType, workflow);
}
