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

export async function deleteRows(
  user: User,
  table: Table,
  rowIds: number[],
): Promise<void> {
  await getClient(user).post(`database/rows/table/${table.id}/batch-delete/`, {
    items: rowIds,
  });
}

export async function listRows(
  user: User,
  table: Table,
): Promise<{ id: number; [k: string]: any }[]> {
  const response = await getClient(user).get(
    `database/rows/table/${table.id}/?user_field_names=true&size=200`,
  );
  return response.data.results;
}
