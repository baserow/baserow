import { getClient } from "../../client";
import { Database } from "./database";
import { User } from "../user";

export class Table {
  constructor(
    public id: number,
    public name: string,
    public database: Database
  ) {}
}

export async function createTable(
  user: User,
  tableName: string,
  database: Database
): Promise<Table> {
  const response: any = await getClient(user).post(
    `database/tables/database/${database.id}/`,
    {
      name: tableName,
    }
  );
  return new Table(response.data.id, response.data.name, database);
}
