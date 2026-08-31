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
  const action = await createWorkflowAction(
    user,
    buttonField,
    "local_baserow_delete_row",
  );
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

/**
 * An action that calls an endpoint outside Baserow. `url` is a formula, so a
 * literal needs its own quotes and a value from the clicked row is read with
 * `get('row.field_1')`.
 */
export async function createHttpRequestAction(
  user: User,
  buttonField: Field,
  options: {
    url: string;
    method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
    timeout?: number;
  },
): Promise<WorkflowAction> {
  const action = await createWorkflowAction(user, buttonField, "http_request");
  return await updateWorkflowAction(user, action, {
    service: {
      type: "http_request",
      http_method: options.method ?? "GET",
      url: options.url,
      timeout: options.timeout ?? 30,
    },
  });
}

/**
 * An action that sends mail through the instance's own SMTP server. A button
 * carries no integration, so there is no other way for it to send.
 */
export async function createEmailAction(
  user: User,
  buttonField: Field,
  options: { to: string; subject: string; body: string },
): Promise<WorkflowAction> {
  const action = await createWorkflowAction(user, buttonField, "smtp_email");
  return await updateWorkflowAction(user, action, {
    service: {
      type: "smtp_email",
      use_instance_smtp_settings: true,
      to_emails: options.to,
      subject: options.subject,
      body: options.body,
      body_type: "plain",
    },
  });
}

/** What one action looks like to the API, including its service. */
export async function getWorkflowAction(
  user: User,
  action: WorkflowAction,
): Promise<any> {
  const actions = await listWorkflowActions(user, action.field);
  return actions.find((candidate) => candidate.id === action.id);
}
