import { getClient } from "../../client";
import { User } from "../user";
import { Database } from "./database";

/** An integration attached to a database application. */
export class DatabaseIntegration {
  constructor(
    public id: number,
    public type: string,
    public name: string,
    public database: Database,
  ) {}
}

/**
 * A Slack bot on the database, the credential a button's Slack action sends
 * through. The token is whatever the caller passes: a made-up one is enough
 * to configure the action, a real one is needed for a click to arrive.
 */
export async function createSlackBotIntegration(
  user: User,
  database: Database,
  options: { name?: string; token: string },
): Promise<DatabaseIntegration> {
  const response: any = await getClient(user).post(
    `application/${database.id}/integrations/`,
    { type: "slack_bot", name: options.name ?? "Bot", token: options.token },
  );
  return new DatabaseIntegration(
    response.data.id,
    response.data.type,
    response.data.name,
    database,
  );
}

export async function listIntegrations(
  user: User,
  database: Database,
): Promise<any[]> {
  const response: any = await getClient(user).get(
    `application/${database.id}/integrations/`,
  );
  return response.data;
}
