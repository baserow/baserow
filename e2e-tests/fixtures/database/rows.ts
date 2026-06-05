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

export async function createRows(
  user: User,
  table: Table,
  rowValues: any,
): Promise<void> {
  await getClient(user).post(
    `database/rows/table/${table.id}/batch/?user_field_names=true`,
    { items: rowValues },
  );
}
