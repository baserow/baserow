import { getClient } from "../../client";
import { faker } from "@faker-js/faker";
import { Database } from "./database";
import { User } from "../user";

export class Table {
  constructor(
    public id: number,
    public name: string,
    public database: Database,
  ) {}
}

export async function updateRows(
  user: User,
  table: Table,
  rowValues: any,
): Promise<void> {
  await getClient(user).patch(
    `database/rows/table/${table.id}/batch/?user_field_names=true`,
    { items: rowValues },
  );
}

/**
 * Fetches a table's rows keyed by field name, used to read back row ids.
 */
export async function getRows(
  user: User,
  table: { id: number },
): Promise<any[]> {
  const response: any = await getClient(user).get(
    `database/rows/table/${table.id}/?user_field_names=true`,
  );
  return response.data.results;
}
