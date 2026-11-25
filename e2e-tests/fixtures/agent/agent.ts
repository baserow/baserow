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

/** An agent answered by the E2E model stub at `E2E_AGENT_MODEL_HOST`. */
export async function createSupportAgent(workspace: Workspace): Promise<Agent> {
  const client = getClient(workspace.user);
  await client.post(`ai-providers/?workspace_id=${workspace.id}`, {
    provider_type: "ollama",
    extra_settings: { host: process.env.E2E_AGENT_MODEL_HOST },
    models: [{ model_identifier: "kuma-e2e", feature_types: ["ai_agent"] }],
  });
  const agent = await createAgent("Customer support", workspace);
  await client.patch(`agent/${agent.id}/configuration/`, {
    instructions: "Help customers with support requests.",
    provider_type: "ollama",
    model_identifier: "kuma-e2e",
  });
  return agent;
}

export async function listAgentTriggers(agent: Agent): Promise<any[]> {
  const response: any = await getClient(agent.workspace.user).get(
    `agent/${agent.id}/triggers/`
  );
  return response.data;
}

export async function createAgentIdentity(
  name: string,
  workspace: Workspace,
  roleUid?: string
): Promise<number> {
  const response: any = await getClient(workspace.user).post(
    `identities/workspace/${workspace.id}/`,
    { name, role_uid: roleUid }
  );
  return response.data.id;
}

export async function setAgentRunIdentity(
  agent: Agent,
  identityId: number
): Promise<void> {
  await getClient(agent.workspace.user).patch(
    `agent/${agent.id}/configuration/`,
    { run_as_subject_type: "auth.User", run_as_subject_id: identityId }
  );
}
