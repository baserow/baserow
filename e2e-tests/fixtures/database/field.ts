import { getClient } from "../../client";
import { User } from "../user";
import { Table } from "./table";

export class Field {
  constructor(
    public id: number,
    public name: string,
    public type: string,
    public table: Table,
    public fieldSettings: any
  ) {}

  get primary(): boolean {
    return this.fieldSettings.primary;
  }
}

export async function createField(
  user: User,
  fieldName: string,
  type: string,
  fieldSettings: any,
  table: Table
): Promise<Field> {
  const response: any = await getClient(user).post(
    `database/fields/table/${table.id}/`,
    {
      name: fieldName,
      type: type,
      ...fieldSettings,
    }
  );
  const field1 = new Field(
    response.data.id,
    response.data.name,
    response.data.type,
    table,
    response.data
  );
  console.log(`created field ${field1.name} in ${field1.table.name}`);
  return field1;
}

export async function updateField(
  user: User,
  fieldName: string,
  type: string,
  fieldSettings: any,
  field: Field
): Promise<Field> {
  const data = {
    name: fieldName,
    type: type,
    ...fieldSettings,
  };
  const response: any = await getClient(user).patch(
    `database/fields/${field.id}/`,
    data
  );
  const f = new Field(
    response.data.id,
    response.data.name,
    response.data.type,
    field.table,
    response.data
  );
  console.log(`update field ${field.name} in ${f.name} in ${f.table.name}`);
  return f;
}

export async function deleteField(user: User, field: Field): Promise<void> {
  console.log(`deleting field ${field.name} in ${field.table.name}`);
  await getClient(user).delete(`database/fields/${field.id}/`);
}

export async function getFieldsForTable(
  user: User,
  table: Table
): Promise<Field[]> {
  const response: any = await getClient(user).get(
    `database/fields/table/${table.id}/`
  );
  return response.data.map((f) => {
    return new Field(f.id, f.name, f.type, table, f);
  });
}

export async function deleteAllNonPrimaryFieldsFromTable(
  user: User,
  table: Table
): Promise<void> {
  (await getFieldsForTable(user, table))
    .filter((f) => !f.primary)
    .forEach((f) => deleteField(user, f));
}
