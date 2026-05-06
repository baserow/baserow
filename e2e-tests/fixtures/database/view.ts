import { getClient } from "../../client";
import { User } from "../user";
import { Table } from "./table";
import { Field } from "./field";

export class View {
  constructor(
    public id: number,
    public name: string,
    public table: Table,
  ) {}
}

export async function getDefaultGridView(
  user: User,
  table: Table,
): Promise<View> {
  const response: any = await getClient(user).get(
    `database/views/table/${table.id}/`,
  );
  const gridView = response.data.find((view: any) => view.type === "grid");
  return new View(gridView.id, gridView.name, table);
}

export async function createViewGroupBy(
  user: User,
  view: View,
  field: Field,
  order = "ASC",
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/group_bys/`, {
    field: field.id,
    order,
  });
}
