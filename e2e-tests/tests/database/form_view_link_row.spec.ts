import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable, Table } from "../../fixtures/database/table";
import { createField, Field } from "../../fixtures/database/field";
import { listRows } from "../../fixtures/database/rows";
import {
  createFormView,
  updateFormFieldOptions,
} from "../../fixtures/database/view";
import { FormPage } from "../../pages/database/formPage";
import { User } from "../../fixtures/user";
import { Workspace } from "../../fixtures/workspace";

// Link-row behaviour on the public form: the "unnamed row" label for
// empty-primary linked rows, and that a picked empty-primary row counts as a
// real selection (not empty) for both visibility filters and required
// validation, matching the backend's many-to-many semantics.

type Scenario = {
  database: any;
  linkedTable: Table;
  targetTable: Table;
  linkField: Field;
  emptyRowId: number;
  namedRowName: string;
};

async function buildScenario(
  user: User,
  workspace: Workspace,
): Promise<Scenario> {
  const database = await createDatabase(user, "Form DB", workspace);

  // Linked table with one named row and one empty-primary row.
  const namedRowName = "Visible Link";
  const linkedTable = await createTable(user, "Places", database, [
    ["Name"],
    [namedRowName],
    [""],
  ]);
  const linkedRows = await listRows(user, linkedTable);
  const emptyRow = linkedRows.find((r) => !r.Name);
  if (!emptyRow) {
    throw new Error("Expected an empty-primary row in the linked table.");
  }

  // Target table that holds the form. Only a primary field for now; each test
  // adds the fields it needs.
  const targetTable = await createTable(user, "Entries", database, [["Title"]]);
  const linkField = await createField(
    user,
    "Place",
    "link_row",
    { link_row_table_id: linkedTable.id },
    targetTable,
  );

  return {
    database,
    linkedTable,
    targetTable,
    linkField,
    emptyRowId: emptyRow.id,
    namedRowName,
  };
}

test.describe("Form view link-row field", () => {
  // Each test creates tables, fields, rows and a form view over the API and
  // then drives a dropdown that fetches its options, so give them more headroom
  // than the default when several run in parallel against one dev stack.
  test.describe.configure({ timeout: 60_000 });

  let user: User;
  let workspace: Workspace;

  test.beforeEach(async ({ workspacePage }) => {
    user = workspacePage.user;
    workspace = workspacePage.workspace;
  });

  test("empty-primary linked rows show the unnamed-row label in the dropdown", async ({
    page,
    goto,
  }) => {
    const s = await buildScenario(user, workspace);
    const view = await createFormView(user, s.targetTable);
    await updateFormFieldOptions(user, view, {
      [s.linkField.id]: { enabled: true, required: false, order: 1 },
    });

    const formPage = new FormPage({ page, goto });
    await formPage.gotoPublic(view.slug);

    await formPage.openLinkDropdown("Place");

    // The empty-primary row renders as "unnamed row {id}" instead of a blank
    // option, alongside the normally-named row.
    await expect(formPage.dropdownOption(s.namedRowName)).toBeVisible();
    await expect(
      formPage.dropdownOption(`unnamed row ${s.emptyRowId}`),
    ).toBeVisible();
  });

  test("picking an empty-primary row reveals a field shown only when the link is not empty", async ({
    page,
    goto,
  }) => {
    const s = await buildScenario(user, workspace);
    const detailsField = await createField(
      user,
      "Details",
      "long_text",
      {},
      s.targetTable,
    );
    const view = await createFormView(user, s.targetTable);
    await updateFormFieldOptions(user, view, {
      [s.linkField.id]: { enabled: true, required: false, order: 1 },
      [detailsField.id]: {
        enabled: true,
        required: false,
        order: 2,
        show_when_matching_conditions: true,
        condition_type: "AND",
        conditions: [{ field: s.linkField.id, type: "not_empty", value: "" }],
      },
    });

    const formPage = new FormPage({ page, goto });
    await formPage.gotoPublic(view.slug);

    // Hidden while nothing is selected.
    expect(await formPage.isFieldVisible("Details")).toBe(false);

    // Picking the empty-primary row counts as a real selection, so the
    // dependent field appears.
    await formPage.pickLinkOption("Place", `unnamed row ${s.emptyRowId}`);
    await expect(formPage.fieldWrapper("Details")).toBeVisible();
  });

  test("a required, untouched, empty field blocks submission", async ({
    page,
    goto,
  }) => {
    const s = await buildScenario(user, workspace);
    const durationField = await createField(
      user,
      "Duration",
      "duration",
      { duration_format: "h:mm" },
      s.targetTable,
    );
    const view = await createFormView(user, s.targetTable);
    await updateFormFieldOptions(user, view, {
      [durationField.id]: { enabled: true, required: true, order: 1 },
    });

    const formPage = new FormPage({ page, goto });
    const submitCount = formPage.trackSubmitRequests();
    await formPage.gotoPublic(view.slug);

    // Submit without touching the required duration field. Client-side
    // validation must block it rather than firing a request the backend
    // rejects.
    await formPage.submit();
    await page.waitForTimeout(1000);
    expect(submitCount()).toBe(0);
    await formPage.expectNotSubmitted();

    // Blocking silently is not enough: the respondent needs to see why the
    // form did not submit, so the required error must be visible.
    await expect(formPage.requiredError("Duration")).toBeVisible();
  });

  test("a required link field is satisfied by an empty-primary row", async ({
    page,
    goto,
  }) => {
    const s = await buildScenario(user, workspace);
    const view = await createFormView(user, s.targetTable);
    await updateFormFieldOptions(user, view, {
      [s.linkField.id]: { enabled: true, required: true, order: 1 },
    });

    const formPage = new FormPage({ page, goto });
    await formPage.gotoPublic(view.slug);

    await formPage.pickLinkOption("Place", `unnamed row ${s.emptyRowId}`);
    await formPage.submit();

    // A picked empty-primary row is a real selection, so the required link
    // field is satisfied and the form submits.
    await formPage.expectSubmitted();
  });
});
