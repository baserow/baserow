import { getClient } from "../../client";
import { Database } from "./database";
import { User } from "../user";

export class Table {
  constructor(
    public id: number,
    public name: string,
    public database: Database
  ) { }
}

export class Row {
  constructor(public id: number) { }
}

export async function createRows(
  user: User,
  table: Table,
  rowValues: any
): Promise<Row[]> {
  const response = await getClient(user).post(
    `database/rows/table/${table.id}/batch/?user_field_names=true`,
    { items: rowValues }
  );
  const newRowsData = response.data
  return newRowsData.items.map((item: any) => new Row(item.id))
}

export async function updateRows(
  user: User,
  table: Table,
  rowValues: any
): Promise<void> {
  await getClient(user).patch(
    `database/rows/table/${table.id}/batch/?user_field_names=true`,
    { items: rowValues }
  );
}

export async function deleteRows(
  user: User,
  table: Table,
  rowIds: number[],
): Promise<void> {
  await getClient(user).post(
    `database/rows/table/${table.id}/batch-delete/?user_field_names=true`,
    { items: rowIds }
  );
}
