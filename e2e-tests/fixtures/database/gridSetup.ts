import { User, createUser } from "../user";
import { createWorkspace } from "../workspace";
import { Database, createDatabase } from "./database";
import { Table, createTable } from "./table";
import {
  View,
  getDefaultGridView,
  ensureViewFieldOptions,
  createViewFilter,
  createViewSort,
  createViewGroupBy,
  setViewFieldAggregation,
} from "./view";
import {
  Field,
  createField,
  getFieldsForTable,
  deleteAllNonPrimaryFieldsFromTable,
} from "./field";
import { createRows, deleteRows, listRows } from "./rows";

// Field spec

export type FieldType =
  | "text"
  | "number"
  | "email"
  | "boolean"
  | "date"
  | "single_select"
  | "long_text"
  | "formula";

export type SelectOptionSpec =
  | string
  | {
      value: string;
      color?: string;
    };

export interface FieldSpec {
  name: string;
  type: FieldType;
  /** For single_select: option labels or explicit value/color pairs. */
  options?: SelectOptionSpec[];
  /** Any extra field-type-specific settings passed directly to the API */
  settings?: Record<string, unknown>;
}

// Filter / sort spec

export interface FilterSpec {
  /** Field name matching a key in `fields` */
  fieldName: string;
  /** Baserow filter type, e.g. "equal", "contains", "higher_than", "single_select_equal" */
  type: string;
  value: string;
}

export interface SortSpec {
  fieldName: string;
  order?: "ASC" | "DESC";
}

export interface GroupBySpec {
  fieldName: string;
  order?: "ASC" | "DESC";
}

export interface AggregationSpec {
  fieldName: string;
  /** Aggregation type, e.g. "sum", "min", "max", "average". */
  type: string;
  /** Raw aggregation type; defaults to `type` when the two are the same. */
  rawType?: string;
}

// Setup options

export interface GridSetupOptions {
  /** Human-readable database name (defaults to "TestDb") */
  dbName?: string;
  /** Human-readable table name (defaults to "Test") */
  tableName?: string;
  /** Non-primary fields to create (the primary Name field is always created by Baserow) */
  fields: FieldSpec[];
  /**
   * Seed rows. Keys are field names (matching `fields[].name` or the primary field
   * name "Name"). For single_select fields you can pass the option label string; it will be
   * resolved to the option id automatically.
   */
  rows?: Record<string, unknown>[];
  /** View-level filters applied via the API before the test starts */
  filters?: FilterSpec[];
  /** View-level sorts applied via the API before the test starts */
  sorts?: SortSpec[];
  /** View-level group-bys applied via the API before the test starts */
  groupBys?: GroupBySpec[];
  /** Per-column "Summarize" aggregations applied via the API before the test starts */
  aggregations?: AggregationSpec[];
}

// Setup result

export interface GridSetupResult {
  /** The isolated user created for this test suite - pass to GridPage */
  user: User;
  database: Database;
  table: Table;
  view: View;
  /** Fields by name - includes both the primary field ("Name") and all created fields */
  fieldByName: Record<string, Field>;
  /** Ids of the seeded rows in creation order */
  rowIds: number[];
  /**
   * Resolve a single_select option label to its BE-assigned integer id.
   * Throws if the field or option is not found.
   */
  getOptionId(fieldName: string, optionLabel: string): number;
}

// Main helper

function normalizeSelectOption(option: SelectOptionSpec): {
  value: string;
  color: string;
} {
  if (typeof option === "string") {
    return { value: option, color: "blue" };
  }

  return { value: option.value, color: option.color ?? "blue" };
}

/**
 * Creates a complete, isolated grid environment for a test suite.
 *
 * Creates its own user and workspace so `beforeAll` needs no Playwright
 * fixtures. `page` and `context` are test-scoped and cannot be used in
 * `beforeAll`. Navigation is done in `beforeEach` using the returned `user`.
 *
 * Example:
 * ```typescript
 * let g: GridSetupResult
 *
 * test.beforeAll(async () => {
 *   g = await setupGrid({
 *     fields: [
 *       { name: "Score", type: "number" },
 *       { name: "Status", type: "single_select", options: ["Done", "In Progress"] },
 *     ],
 *     rows: [
 *       { Name: "Alice", Score: 10, Status: "Done" },
 *       { Name: "Bob",   Score: 20, Status: "In Progress" },
 *     ],
 *   })
 * })
 *
 * test.beforeEach(async ({ page }) => {
 *   const grid = new GridPage(page, g.user)
 *   await grid.goTo(g.database, g.table)
 * })
 * ```
 */
export async function setupGrid(
  options: GridSetupOptions,
): Promise<GridSetupResult> {
  const user = await createUser();
  const workspace = await createWorkspace(user);
  // 1. Create isolated database + table
  const database = await createDatabase(
    user,
    options.dbName ?? "TestDb",
    workspace,
  );
  const table = await createTable(user, options.tableName ?? "Test", database);

  // Remove the extra fields Baserow creates by default (keeps only the primary field)
  await deleteAllNonPrimaryFieldsFromTable(user, table);

  // Remove the two default empty rows Baserow inserts on table creation
  const defaultRows = await listRows(user, table);
  if (defaultRows.length > 0) {
    await deleteRows(
      user,
      table,
      defaultRows.map((r) => r.id),
    );
  }

  // 2. Create the requested fields
  const fieldByName: Record<string, Field> = {};

  // Fetch the primary field so callers can reference it by name
  const existingFields = await getFieldsForTable(user, table);
  for (const f of existingFields) {
    fieldByName[f.name] = f;
  }

  for (const spec of options.fields) {
    const apiSettings: Record<string, unknown> = { ...(spec.settings ?? {}) };

    if (spec.type === "single_select" && spec.options) {
      apiSettings.select_options = spec.options.map(normalizeSelectOption);
    }

    fieldByName[spec.name] = await createField(
      user,
      spec.name,
      spec.type,
      apiSettings,
      table,
    );
  }

  // 3. Refresh to get BE-assigned select option IDs
  const optionIdMap: Record<string, Record<string, number>> = {};
  const refreshedFields = await getFieldsForTable(user, table);

  for (const spec of options.fields) {
    if (spec.type === "single_select" && spec.options) {
      const refreshed = refreshedFields.find(
        (f) => f.id === fieldByName[spec.name].id,
      );
      const opts = refreshed?.fieldSettings?.select_options ?? [];
      optionIdMap[spec.name] = Object.fromEntries(
        opts.map((o: { value: string; id: number }) => [o.value, o.id]),
      );
    }
  }

  const getOptionId = (fieldName: string, optionLabel: string): number => {
    const id = optionIdMap[fieldName]?.[optionLabel];
    if (id === undefined) {
      throw new Error(
        `Option "${optionLabel}" not found in field "${fieldName}". ` +
          `Available: ${Object.keys(optionIdMap[fieldName] ?? {}).join(", ")}`,
      );
    }
    return id;
  };

  // 4. Seed rows - resolve single_select labels to option ids automatically
  const rowIds: number[] = [];

  if (options.rows?.length) {
    const fieldSpecByName = Object.fromEntries(
      options.fields.map((s) => [s.name, s]),
    );

    const resolved = options.rows.map((row) => {
      const out: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(row)) {
        const spec = fieldSpecByName[key];
        if (spec?.type === "single_select" && typeof value === "string") {
          out[key] = getOptionId(key, value);
        } else {
          out[key] = value;
        }
      }
      return out;
    });

    const created = await createRows(user, table, resolved);
    rowIds.push(...created.map((r) => r.id));
  }

  // 5. Get the default grid view
  const view = await getDefaultGridView(user, table);
  await ensureViewFieldOptions(user, view);

  // 6. Apply view-level filters
  for (const f of options.filters ?? []) {
    const fieldSpec = options.fields.find((s) => s.name === f.fieldName);
    const value =
      fieldSpec?.type === "single_select" && typeof f.value === "string"
        ? String(getOptionId(f.fieldName, f.value))
        : f.value;

    await createViewFilter(user, view, fieldByName[f.fieldName], f.type, value);
  }

  // 7. Apply view-level sorts
  for (const s of options.sorts ?? []) {
    await createViewSort(
      user,
      view,
      fieldByName[s.fieldName],
      s.order ?? "ASC",
    );
  }

  // 8. Apply view-level group-bys
  for (const g of options.groupBys ?? []) {
    await createViewGroupBy(
      user,
      view,
      fieldByName[g.fieldName],
      g.order ?? "ASC",
    );
  }

  // 9. Apply per-column "Summarize" aggregations
  for (const a of options.aggregations ?? []) {
    await setViewFieldAggregation(
      user,
      view,
      fieldByName[a.fieldName],
      a.type,
      a.rawType ?? a.type,
    );
  }

  return { user, database, table, view, fieldByName, rowIds, getOptionId };
}

// Row reset helper

/**
 * Delete all existing rows in the table and recreate them from `newRows`.
 * Call in `beforeEach` for tests that mutate row data so each test starts
 * from a clean, known state.
 *
 * Resolves single_select labels to option IDs automatically using the
 * `getOptionId` function from the setup result.
 *
 * Example:
 * ```typescript
 * test.beforeEach(async ({ page }) => {
 *   await resetRows(g, [
 *     { Name: "Alice", Score: 10 },
 *     { Name: "Bob",   Score: 20 },
 *   ])
 *   const grid = new GridPage(page, g.user)
 *   await grid.goTo(g.database, g.table)
 * })
 * ```
 */
export async function resetRows(
  g: GridSetupResult,
  newRows: Record<string, unknown>[],
): Promise<void> {
  const existing = await listRows(g.user, g.table);
  if (existing.length > 0) {
    await deleteRows(
      g.user,
      g.table,
      existing.map((r) => r.id),
    );
  }

  if (newRows.length === 0) return;

  // Resolve single_select labels to option IDs
  const resolved = newRows.map((row) => {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(row)) {
      if (
        g.fieldByName[key]?.type === "single_select" &&
        typeof value === "string"
      ) {
        out[key] = g.getOptionId(key, value);
      } else {
        out[key] = value;
      }
    }
    return out;
  });

  await createRows(g.user, g.table, resolved);
}
