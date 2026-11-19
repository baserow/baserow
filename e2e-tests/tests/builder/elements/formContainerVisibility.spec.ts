import type { Request as BrowserRequest } from "@playwright/test";
import { getClient } from "../../../client";
import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { createBuilderWorkflowAction } from "../../../fixtures/builder/builderWorkflowAction";
import { createLocalBaserowIntegration } from "../../../fixtures/builder/integration";
import { createDatabase } from "../../../fixtures/database/database";
import { getFieldsForTable } from "../../../fixtures/database/field";
import { listRows } from "../../../fixtures/database/rows";
import { createTable } from "../../../fixtures/database/table";
import { expect, test } from "../../baserowTest";

/** Read the actual multipart dispatch metadata without intercepting the request. */
async function dispatchMetadata(request: BrowserRequest) {
  const form = await new Request(request.url(), {
    method: "POST",
    headers: request.headers(),
    body: request.postDataBuffer(),
  }).formData();
  return JSON.parse(String(form.get("metadata")));
}

test("ancestor-hidden fields allow form submission without sending their values", async ({
  context,
  builderPagePage,
  workspacePage,
}) => {
  test.setTimeout(90000);
  const user = workspacePage.workspace.user;
  const client = getClient(user);
  const builderPage = builderPagePage.builderPage;
  const database = await createDatabase(
    user,
    "Form results",
    workspacePage.workspace
  );
  const table = await createTable(user, "Submissions", database, [
    ["Name", "Required email", "Optional email"],
  ]);
  const fields = await getFieldsForTable(user, table);
  const integration = await createLocalBaserowIntegration(builderPagePage.builder);
  const form = await createBuilderElement(builderPage, "form_container", {
    submit_button_label: "'Submit form'",
    reset_initial_values_post_submission: false,
  });
  const insideForm = { reference_element_id: form.id, position: "child" };
  const name = await createBuilderElement(builderPage, "input_text", {
    ...insideForm,
    label: "'Name'",
    placeholder: "'Your name'",
    required: true,
  });
  const toggle = await createBuilderElement(builderPage, "checkbox", {
    ...insideForm,
    label: "'Show email fields'",
  });
  const outer = await createBuilderElement(builderPage, "column", {
    ...insideForm,
    column_amount: 1,
    visibility_condition: {
      formula: `get('form_data.${toggle.id}')`,
      mode: "advanced",
    },
  });
  const inner = await createBuilderElement(builderPage, "simple_container", {
    reference_element_id: outer.id,
    position: "child",
    place_in_container: "0",
  });
  const emails = [];
  for (const required of [true, false]) {
    emails.push(
      await createBuilderElement(builderPage, "input_text", {
        reference_element_id: inner.id,
        position: "child",
        label: required ? "'Required email'" : "'Optional email'",
        placeholder: required
          ? "'Required email address'"
          : "'Optional email address'",
        required,
        validation_type: "email",
        default_value: "'invalid-email'",
      })
    );
  }
  const action = await createBuilderWorkflowAction(
    builderPage,
    form,
    "create_row",
    "submit"
  );
  await client.patch(`builder/workflow_action/${action.id}/`, {
    service: {
      type: action.properties.service.type,
      integration_id: integration.id,
      table_id: table.id,
      field_mappings: [name, ...emails].map((element, index) => ({
        field_id: fields[index].id,
        value: `get('form_data.${element.id}')`,
        enabled: true,
      })),
    },
  });
  const { data: grant } = await client.post(
    `builder/preview/${builderPagePage.builder.id}/grant/`,
    { path: builderPage.path },
  );
  const preview = await context.newPage();
  await preview.goto(grant.url, { waitUntil: "networkidle" });
  const submit = preview.getByRole("button", { name: "Submit form", exact: true });
  const requiredEmail = preview.getByPlaceholder("Required email address", {
    exact: true,
  });
  const optionalEmail = preview.getByPlaceholder("Optional email address", {
    exact: true,
  });
  const errors = preview.locator(".ab-form-group__error-message");

  // Hidden descendants must not exempt a visible required input from validation.
  await expect(requiredEmail).toBeHidden();
  await submit.click();
  await expect(errors).toHaveCount(1);
  expect(await listRows(user, table)).toEqual([]);
  await preview.getByPlaceholder("Your name", { exact: true }).fill("Ada");
  await preview.getByRole("checkbox", { name: "Show email fields" }).check();
  await expect(requiredEmail).toHaveValue("invalid-email");
  await expect(optionalEmail).toHaveValue("invalid-email");
  await submit.click();
  await expect(errors).toHaveCount(2);
  expect(await listRows(user, table)).toEqual([]);

  await preview.getByRole("checkbox", { name: "Show email fields" }).uncheck();
  await expect(requiredEmail).toBeHidden();
  await expect(optionalEmail).toBeHidden();
  const hiddenDispatch = preview.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/${action.id}/dispatch/`),
    { timeout: 15000 }
  );
  await submit.click();
  const hiddenResponse = await hiddenDispatch;
  expect(hiddenResponse.status()).toBe(200);
  expect((await dispatchMetadata(hiddenResponse.request())).form_data).toEqual({
    [name.id]: "Ada",
    [toggle.id]: false,
  });
  expect(await listRows(user, table)).toEqual([
    expect.objectContaining({
      Name: "Ada",
      "Required email": "",
      "Optional email": "",
    }),
  ]);

  // Showing the container again must restore validation and submit visible values.
  await preview.getByRole("checkbox", { name: "Show email fields" }).check();
  await submit.click();
  await expect(errors).toHaveCount(2);
  await requiredEmail.fill("required@example.com");
  await optionalEmail.fill("optional@example.com");
  const visibleDispatch = preview.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/${action.id}/dispatch/`),
    { timeout: 15000 }
  );
  await submit.click();
  const visibleResponse = await visibleDispatch;
  expect(visibleResponse.status()).toBe(200);
  expect((await dispatchMetadata(visibleResponse.request())).form_data).toEqual({
    [name.id]: "Ada",
    [toggle.id]: true,
    [emails[0].id]: "required@example.com",
    [emails[1].id]: "optional@example.com",
  });
  expect(await listRows(user, table)).toEqual([
    expect.objectContaining({
      Name: "Ada",
      "Required email": "",
      "Optional email": "",
    }),
    expect.objectContaining({
      Name: "Ada",
      "Required email": "required@example.com",
      "Optional email": "optional@example.com",
    }),
  ]);
});
