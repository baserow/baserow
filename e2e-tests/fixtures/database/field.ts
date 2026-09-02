import { getClient } from "../../client";
import { User } from "../user";
import { Table } from "./table";

export class Field {
  constructor(
    public id: number,
    public name: string,
    public type: string,
    public table: Table,
    public fieldSettings: any,
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
  table: Table,
): Promise<Field> {
  const response: any = await getClient(user).post(
    `database/fields/table/${table.id}/`,
    {
      name: fieldName,
      type: type,
      ...fieldSettings,
    },
  );
  const field1 = new Field(
    response.data.id,
    response.data.name,
    response.data.type,
    table,
    response.data,
  );
  return field1;
}

export async function updateField(
  user: User,
  fieldName: string,
  type: string,
  fieldSettings: any,
  field: Field,
): Promise<Field> {
  const data = {
    name: fieldName,
    type: type,
    ...fieldSettings,
  };
  const response: any = await getClient(user).patch(
    `database/fields/${field.id}/`,
    data,
  );
  const f = new Field(
    response.data.id,
    response.data.name,
    response.data.type,
    field.table,
    response.data,
  );
  return f;
}

export async function deleteField(user: User, field: Field): Promise<void> {
  await getClient(user).delete(`database/fields/${field.id}/`);
}

export async function getFieldsForTable(
  user: User,
  table: Table,
): Promise<Field[]> {
  const response: any = await getClient(user).get(
    `database/fields/table/${table.id}/`,
  );
  return response.data.map((f) => {
    return new Field(f.id, f.name, f.type, table, f);
  });
}

export async function deleteAllNonPrimaryFieldsFromTable(
  user: User,
  table: Table,
): Promise<void> {
  const fields = (await getFieldsForTable(user, table)).filter(
    (f) => !f.primary,
  );
  await Promise.all(fields.map((f) => deleteField(user, f)));
}

/**
 * Duplicates a field and waits for the copy to exist. Duplicating runs as a
 * job, so the field is not there the moment the request returns.
 *
 * The job is followed rather than the table's field list. The name the copy is
 * expected to take can already belong to a field an earlier test left behind,
 * and a failed job would only ever be reported as a copy that never appeared.
 */
export async function duplicateField(
  user: User,
  field: Field,
  options: { copyData?: boolean } = {},
): Promise<Field> {
  const client = getClient(user);
  const job: any = await client.post(
    `database/fields/${field.id}/duplicate/async/`,
    { duplicate_data: options.copyData ?? false },
  );

  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const poll: any = await client.get(`jobs/${job.data.id}/`);
    if (poll.data.state === "failed") {
      throw new Error(
        `Duplicating "${field.name}" failed: ${
          poll.data.human_readable_error || ""
        }`,
      );
    }
    if (poll.data.state === "finished") {
      return poll.data.duplicated_field as Field;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Duplicating "${field.name}" did not finish in time`);
}
