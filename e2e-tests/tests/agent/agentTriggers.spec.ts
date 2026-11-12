// Firing needs Celery beat, which the e2e stack lacks; dispatcher tests cover it.
import { expect, test } from "../baserowTest";
import {
  Agent,
  createAgent,
  listAgentTriggers,
} from "../../fixtures/agent/agent";
import { AgentPage } from "../../pages/agent/agentPage";

// The section's copy, from web-frontend/modules/agent/locales/en.json.
const COPY = {
  section: "When it runs",
  addTrigger: "Add trigger",
  enabled: "Trigger enabled",
  deleteTrigger: "Delete trigger",
  empty: "Without a trigger the agent only runs when you chat with it.",
};
// Service type name, from web-frontend/modules/integrations/locales/en.json.
const PERIODIC = "Periodic trigger";

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
});
