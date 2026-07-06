import { getClient } from "../../client";
import { User } from "../user";
import { Table } from "./table";
import { Field } from "./field";

export class View {
  constructor(
    public id: number,
    public name: string,
    public type: string,
    public slug: string,
    public table: Table,
  ) {}
}

/**
 * Creates a form view. With `isPublic` it is shared so `/form/{slug}` is
 * reachable without authentication, the way the e2e tests open it.
 */
export async function createFormView(
  user: User,
  table: Table,
  {
    isPublic = true,
    name = "Form",
  }: { isPublic?: boolean; name?: string } = {},
): Promise<View> {
  const response: any = await getClient(user).post(
    `database/views/table/${table.id}/`,
    { name, type: "form" },
  );
  let data = response.data;
  if (isPublic && !data.public) {
    const patched: any = await getClient(user).patch(
      `database/views/${data.id}/`,
      { public: true },
    );
    data = patched.data;
  }
  return new View(data.id, data.name, data.type, data.slug, table);
}

/**
 * One condition controlling a field's visibility: `field` is the field it
 * reads, `type` is a view filter type like "not_empty", and `value` is the
 * comparison value (blank for empty/not_empty).
 */
export type FormFieldCondition = {
  field: number;
  type: string;
  value?: string;
};

export type FormFieldOptions = {
  enabled?: boolean;
  required?: boolean;
  order?: number;
  name?: string;
  description?: string;
  show_when_matching_conditions?: boolean;
  condition_type?: "AND" | "OR";
  conditions?: FormFieldCondition[];
};

/**
 * Updates the form field options keyed by field id, like the
 * `PATCH database/views/{id}/field-options/` request the frontend sends.
 *
 * Each condition needs an `id`; the backend reads an unknown id as a new
 * condition, so we assign temporary ids here and callers can omit them.
 */
export async function updateFormFieldOptions(
  user: User,
  view: View,
  fieldOptions: Record<number, FormFieldOptions>,
): Promise<void> {
  let tempConditionId = 0;
  const payload: Record<number, any> = {};
  for (const [fieldId, options] of Object.entries(fieldOptions)) {
    payload[Number(fieldId)] = {
      ...options,
      ...(options.conditions
        ? {
            conditions: options.conditions.map((condition) => ({
              id: (tempConditionId -= 1),
              value: "",
              ...condition,
            })),
          }
        : {}),
    };
  }
  await getClient(user).patch(`database/views/${view.id}/field-options/`, {
    field_options: payload,
  });
}

/**
 * Configure a column's "Summarize" aggregation on a grid view, the same
 * field-options PATCH the footer/group-header picker sends.
 */
export async function setViewFieldAggregation(
  user: User,
  view: View,
  field: Field,
  aggregationType: string,
  aggregationRawType: string,
): Promise<void> {
  await getClient(user).patch(`database/views/${view.id}/field-options/`, {
    field_options: {
      [field.id]: {
        aggregation_type: aggregationType,
        aggregation_raw_type: aggregationRawType,
      },
    },
  });
}

export async function getDefaultGridView(
  user: User,
  table: Table,
): Promise<View> {
  const response: any = await getClient(user).get(
    `database/views/table/${table.id}/`,
  );
  const gridView = response.data.find((view: any) => view.type === "grid");
  return new View(
    gridView.id,
    gridView.name,
    gridView.type,
    gridView.slug,
    table,
  );
}

export async function createGridView(
  user: User,
  table: Table,
  { name = "Grid" }: { name?: string } = {},
): Promise<View> {
  const response: any = await getClient(user).post(
    `database/views/table/${table.id}/`,
    { name, type: "grid" },
  );
  const data = response.data;
  const view = new View(data.id, data.name, data.type, data.slug, table);
  await ensureViewFieldOptions(user, view);
  return view;
}

export async function ensureViewFieldOptions(
  user: User,
  view: View,
): Promise<void> {
  await getClient(user).get(`database/views/${view.id}/field-options/`);
}

export async function createViewFilter(
  user: User,
  view: View,
  field: Field,
  type: string,
  value: string,
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/filters/`, {
    field: field.id,
    type,
    value,
  });
}

export async function createViewSort(
  user: User,
  view: View,
  field: Field,
  order: "ASC" | "DESC" = "ASC",
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/sortings/`, {
    field: field.id,
    order,
  });
}

export async function createViewGroupBy(
  user: User,
  view: View,
  field: Field,
  order: "ASC" | "DESC" = "ASC",
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/group_bys/`, {
    field: field.id,
    order,
  });
}

export interface ViewDecorationPayload {
  type: string;
  value_provider_type?: string;
  value_provider_conf?: Record<string, unknown>;
  order?: number;
}

export async function patchView(
  user: User,
  view: View,
  values: Record<string, unknown>,
): Promise<void> {
  await getClient(user).patch(`database/views/${view.id}/`, values);
}

export async function createViewDecoration(
  user: User,
  view: View,
  values: ViewDecorationPayload,
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/decorations/`, values);
}
