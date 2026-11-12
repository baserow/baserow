// Firing needs Celery beat or an AI provider, which the e2e stack lacks.
import { Locator, Page } from "@playwright/test";
import { expect, test } from "../baserowTest";
import {
  Agent,
  createAgent,
  createAgentIdentity,
  listAgentTriggers,
  setAgentRunIdentity,
} from "../../fixtures/agent/agent";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { AgentPage } from "../../pages/agent/agentPage";

// The section's copy, from web-frontend/modules/agent/locales/en.json.
const COPY = {
  section: "When it runs",
  addTrigger: "Add trigger",
  enabled: "Trigger enabled",
  deleteTrigger: "Delete trigger",
  empty: "Without a trigger the agent only runs when you chat with it.",
  dataProvides: /^Data it provides/,
};
// Trigger, group and data names, from the agent and integrations en.json.
const PERIODIC = "Periodic trigger";
const LOCAL_BASEROW = "Local Baserow";
const ROWS_CREATED = "Rows are created";
const ROW_DATA = ["Rows", "Count", "Table", "Fired at"];

// The service form's dropdowns are found by the label of their form group.
async function choose(
  page: Page,
  section: Locator,
  label: string,
  option: string
): Promise<void> {
  await section
    .locator(".control")
    .filter({ has: page.locator(".control__label", { hasText: label }) })
    .locator(".dropdown__selected")
    .click();
  await page
    .locator(".select__item")
    .getByText(option, { exact: true })
    .click();
}

let agent: Agent;
let agentPage: AgentPage;

test.describe("Agent triggers", () => {
  test.beforeEach(async ({ page, goto, workspacePage }) => {
    agent = await createAgent("Trigger agent", workspacePage.workspace);
    agentPage = new AgentPage({ page, goto }, agent);
    await agentPage.goto();
  });

  test("adds, schedules, switches off and deletes a periodic trigger", async ({
    page,
  }) => {
    const section = await agentPage.openSection(COPY.section);
    await expect(section.getByText(COPY.empty)).toBeVisible();

    const created = agentPage.waitForTriggerResponse("POST");
    await section.getByRole("button", { name: COPY.addTrigger }).click();
    await page.getByText(PERIODIC, { exact: true }).click();
    const createdResponse = await created;
    expect(createdResponse.status()).toBe(200);
    const trigger = await createdResponse.json();
    expect(trigger).toMatchObject({
      type: "periodic",
      enabled: true,
      service: { interval: "DAY", hour: 9, minute: 0 },
    });
    await expect(section.getByText(/^Every day at 09:00/)).toBeVisible();

    const scheduled = agentPage.waitForTriggerResponse(
      "PATCH",
      (body) => body?.service?.interval === "WEEK"
    );
    await section
      .locator(".control", { hasText: "Interval" })
      .locator(".dropdown__selected")
      .click();
    await page
      .locator(".select__item")
      .getByText("Every week", { exact: true })
      .click();
    expect((await scheduled).status()).toBe(200);
    expect(await listAgentTriggers(agent)).toMatchObject([
      { id: trigger.id, enabled: true, service: { interval: "WEEK" } },
    ]);

    const enabledSwitch = section.getByRole("switch", { name: COPY.enabled });
    await expect(enabledSwitch).toHaveAttribute("aria-checked", "true");
    const switchedOff = agentPage.waitForTriggerResponse(
      "PATCH",
      (body) => body?.enabled === false
    );
    await enabledSwitch.click();
    expect((await switchedOff).status()).toBe(200);
    await expect(enabledSwitch).toHaveAttribute("aria-checked", "false");
    expect((await listAgentTriggers(agent))[0].enabled).toBe(false);

    const deleted = agentPage.waitForTriggerResponse("DELETE");
    await section.getByRole("button", { name: COPY.deleteTrigger }).click();
    expect((await deleted).status()).toBe(204);
    await expect(section.getByText(COPY.empty)).toBeVisible();
    expect(await listAgentTriggers(agent)).toEqual([]);
  });

  test("adds a rows trigger on a table its identity reads, then switches it off and deletes it", async ({
    page,
  }) => {
    const { user } = agent.workspace;
    const database = await createDatabase(user, "Sales", agent.workspace);
    const table = await createTable(user, "Orders", database, [
      ["Name"],
      ["Horse"],
    ]);
    await setAgentRunIdentity(
      agent,
      await createAgentIdentity("Reader", agent.workspace)
    );
    await agentPage.goto();
    const section = await agentPage.openSection(COPY.section);

    const created = agentPage.waitForTriggerResponse("POST");
    await section.getByRole("button", { name: COPY.addTrigger }).click();
    const picker = page.locator(".agent-trigger-picker");
    await picker
      .locator(".grouped-menu__navigation")
      .getByText(LOCAL_BASEROW, { exact: true })
      .click();
    await picker
      .locator(".grouped-menu__actions")
      .getByText(ROWS_CREATED, { exact: true })
      .click();
    const createdResponse = await created;
    expect(createdResponse.status()).toBe(200);
    const trigger = await createdResponse.json();
    expect(trigger).toMatchObject({
      type: "local_baserow_rows_created",
      enabled: true,
      on_overlap: "wait",
      batch_size: 20,
    });

    const picked = agentPage.waitForTriggerResponse(
      "PATCH",
      (body) => body?.service?.table_id === table.id
    );
    await choose(page, section, "Database", "Sales");
    await choose(page, section, "Table", "Orders");
    expect((await picked).status()).toBe(200);
    expect(await listAgentTriggers(agent)).toMatchObject([
      { id: trigger.id, service: { table_id: table.id } },
    ]);

    await section.getByRole("button", { name: COPY.dataProvides }).click();
    await expect(
      section.locator(".agent-trigger-card__schema-list li > span:first-child")
    ).toHaveText(ROW_DATA);

    const enabledSwitch = section.getByRole("switch", { name: COPY.enabled });
    const switchedOff = agentPage.waitForTriggerResponse(
      "PATCH",
      (body) => body?.enabled === false
    );
    await enabledSwitch.click();
    expect((await switchedOff).status()).toBe(200);
    await expect(enabledSwitch).toHaveAttribute("aria-checked", "false");

    const deleted = agentPage.waitForTriggerResponse("DELETE");
    await section.getByRole("button", { name: COPY.deleteTrigger }).click();
    expect((await deleted).status()).toBe(204);
    await expect(section.getByText(COPY.empty)).toBeVisible();
    expect(await listAgentTriggers(agent)).toEqual([]);
  });
});
