import { getClient } from "../../client";
import { Database } from "./database";
import { User } from "../user";

export class Table {
  constructor(
    public id: number,
    public name: string,
    public database: Database,
  ) {}
}

/**
 * Creates a table with explicit contents. The first row of `data` is the field
 * names, so `[["Name"], ["First"], [""]]` makes a "Name" field with two rows,
 * one named and one with an empty primary. Passing `data` skips the example
 * fields and rows the backend would otherwise generate.
 */
export async function createTable(
  user: User,
  tableName: string,
  database: Database,
  data?: string[][],
): Promise<Table> {
  const response: any = await getClient(user).post(
    `database/tables/database/${database.id}/`,
    {
      name: tableName,
      ...(data ? { data, first_row_header: true } : {}),
    },
  );
  return new Table(response.data.id, response.data.name, database);
}
