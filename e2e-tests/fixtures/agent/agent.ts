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

export async function createAgentIdentity(
  name: string,
  workspace: Workspace
): Promise<number> {
  const response: any = await getClient(workspace.user).post(
    `agents/workspace/${workspace.id}/`,
    { name }
  );
  return response.data.id;
}

export async function setAgentRunIdentity(
  agent: Agent,
  identityId: number
): Promise<void> {
  await getClient(agent.workspace.user).patch(
    `agent/${agent.id}/configuration/`,
    { run_as_subject_type: "core.Agent", run_as_subject_id: identityId }
  );
}
