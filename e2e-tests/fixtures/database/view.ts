import { getClient } from "../../client";
import { User } from "../user";
import { Table } from "./table";

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
