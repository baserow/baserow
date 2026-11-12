import { getClient } from "../../client";
import { Workspace } from "../workspace";

export class Agent {
  constructor(
    public id: number,
    public name: string,
    public workspace: Workspace
  ) {}
}

export async function createAgent(
  name: string,
  workspace: Workspace
): Promise<Agent> {
  const response: any = await getClient(workspace.user).post(
    `applications/workspace/${workspace.id}/`,
    { name, type: "agent" }
  );
  return new Agent(response.data.id, response.data.name, workspace);
}

export async function listAgentTriggers(agent: Agent): Promise<any[]> {
  const response: any = await getClient(agent.workspace.user).get(
    `agent/${agent.id}/triggers/`
  );
  return response.data;
}
