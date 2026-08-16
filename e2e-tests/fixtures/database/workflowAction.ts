import { getClient } from "../../client";
import { User } from "../user";
import { Field } from "./field";
import { Table } from "./table";

export class WorkflowAction {
  constructor(
    public id: number,
    public type: string,
    public field: Field,
    public data: any,
  ) {}
}

/** A single `field_id -> formula` write in an upsert row service. */
export interface FieldMapping {
  field: Field;
  /** A Baserow formula, so a literal needs its own quotes: `"'done'"`. */
  value: string;
  enabled?: boolean;
}

export async function createWorkflowAction(
  user: User,
  field: Field,
  type: string,
): Promise<WorkflowAction> {
  const response: any = await getClient(user).post(
    `database/field/${field.id}/workflow_actions/`,
    { type },
  );
  return new WorkflowAction(
    response.data.id,
    response.data.type,
    field,
    response.data,
  );
}

async function updateWorkflowAction(
  user: User,
  action: WorkflowAction,
  values: Record<string, unknown>,
): Promise<WorkflowAction> {
  const response: any = await getClient(user).patch(
    `database/workflow_action/${action.id}/`,
    values,
  );
  return new WorkflowAction(
    response.data.id,
    response.data.type,
    action.field,
    response.data,
  );
}

export async function listWorkflowActions(
  user: User,
  field: Field,
): Promise<any[]> {
  const response: any = await getClient(user).get(
    `database/field/${field.id}/workflow_actions/`,
  );
  return response.data;
}

/**
 * A create or update row action on `table`. Leave `rowId` out to create a row;
 * pass `"get('row.id')"` to target the clicked row.
 */
export async function createRowAction(
  user: User,
  buttonField: Field,
  options: {
    type?: "local_baserow_create_row" | "local_baserow_update_row";
    table: Table;
    rowId?: string;
    fieldMappings: FieldMapping[];
  },
): Promise<WorkflowAction> {
  const action = await createWorkflowAction(
    user,
    buttonField,
    options.type ?? "local_baserow_update_row",
  );
  return await updateWorkflowAction(user, action, {
    service: {
      type: "local_baserow_upsert_row",
      table_id: options.table.id,
      row_id: options.rowId ?? "",
      field_mappings: options.fieldMappings.map((mapping) => ({
        field_id: mapping.field.id,
        value: mapping.value,
        enabled: mapping.enabled ?? true,
      })),
    },
  });
}

/**
 * A delete row action. `rowId` is a formula, so `"get('row.id')"` targets the
 * clicked row and an array formula deletes several.
 */
export async function createDeleteRowAction(
  user: User,
  buttonField: Field,
  options: { table: Table; rowId: string },
): Promise<WorkflowAction> {
  const action = await createWorkflowAction(user, buttonField, "local_baserow_delete_row");
  return await updateWorkflowAction(user, action, {
    service: {
      type: "local_baserow_delete_row",
      table_id: options.table.id,
      row_id: options.rowId,
    },
  });
}

/** An action the browser runs itself, rather than the dispatch running it. */
export async function createOpenUrlAction(
  user: User,
  buttonField: Field,
  options: { url: string; target?: "self" | "blank" },
): Promise<WorkflowAction> {
  const action = await createWorkflowAction(user, buttonField, "open_url");
  return await updateWorkflowAction(user, action, {
    url: options.url,
    target: options.target ?? "self",
  });
}
