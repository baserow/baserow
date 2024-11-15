import { getClient } from "../../client";
import { User } from "./../user";
import { Workspace } from "./../workspace";

export class Database {
  constructor(
    public id: number,
    public name: string,
    public workspace: Workspace
  ) {}
}

export async function createDatabase(
  user: User,
  databaseName: string,
  workspace: Workspace
): Promise<Database> {
  const response: any = await getClient(user).post(
    `applications/workspace/${workspace.id}/`,
    {
      name: databaseName,
      type: "database",
    }
  );
  return new Database(response.data.id, response.data.name, workspace);
}
