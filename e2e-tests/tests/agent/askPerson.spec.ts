import { getClient } from "../../client";
import { Agent, createSupportAgent } from "../../fixtures/agent/agent";
import { AgentPage } from "../../pages/agent/agentPage";
import { expect, test } from "../baserowTest";

test.skip(
  !process.env.E2E_AGENT_MODEL_HOST,
  "Needs the E2E model stub reachable by the agent worker."
);
// Trigger delivery and model replies share the E2E stack's single Celery worker.
const workerTimeout = 60_000;
test.describe.configure({ timeout: 180_000 });

// The model stub asks only when the trigger message carries "E2E ask a person".
const SUBJECT = "E2E ask a person: refund request";
const TRIGGER_NAME = "Ticket received";

async function createTicketTrigger(agent: Agent) {
  const { data } = await getClient(agent.workspace.user).post(
    `agent/${agent.id}/triggers/`,
    {
      type: "http_trigger",
      name: TRIGGER_NAME,
      message: "get('trigger.body.subject')",
    }
  );
  return data;
}

async function fireTicketTrigger(trigger: { service: { uid: string } }) {
  await getClient().post(`webhooks/${trigger.service.uid}/`, {
    subject: SUBJECT,
  });
}

async function lastReply(agent: Agent) {
  const client = getClient(agent.workspace.user);
  const { data: conversations } = await client.get(
    `agent/${agent.id}/conversations/`
  );
  const [conversation] = conversations.results;
  if (!conversation) return null;
  const { data } = await client.get(
    `agent/${agent.id}/conversations/${conversation.uuid}/messages/`
  );
  return data.results.at(-1);
}

test("a triggered run asks a person and continues with the answer", async ({
  page,
  goto,
  workspacePage,
}) => {
  const agent = await createSupportAgent(workspacePage.workspace);
  const trigger = await createTicketTrigger(agent);
  expect(trigger.may_ask_person).toBe(true);
  await fireTicketTrigger(trigger);
  await expect
    .poll(() => lastReply(agent), { timeout: workerTimeout })
    .toMatchObject({
      role: "assistant",
      approvals: [{ tool: "ask_person", status: "pending" }],
    });

  const agentPage = new AgentPage({ page, goto }, agent);
  await agentPage.goto();
  await page
    .locator(".agent-conversations__row", { hasText: SUBJECT })
    .locator(".agent-conversations__item")
    .click();
  const question = page.locator(".agent-question");
  await expect(question).toContainText("Customer support has a question");
  await expect(question).toContainText("Which customer is this about?");
  await question.getByRole("textbox", { name: "Your answer" }).fill("Acme");
  await question.getByRole("button", { name: "Send answer" }).click();

  await expect(page.locator(".agent-chat")).toContainText("Done for Acme.", {
    timeout: workerTimeout,
  });
  await expect(question).toContainText("Answered");
  await expect(question.locator(".agent-question__answer")).toHaveText("Acme");
  await expect
    .poll(() => lastReply(agent), { timeout: workerTimeout })
    .toMatchObject({
      content: "Done for Acme.",
      status: "completed",
      approvals: [{ tool: "ask_person", status: "approved", answer: "Acme" }],
    });
});

test("a trigger switched off from asking never offers the question tool", async ({
  page,
  goto,
  workspacePage,
}) => {
  const agent = await createSupportAgent(workspacePage.workspace);
  const trigger = await createTicketTrigger(agent);
  const agentPage = new AgentPage({ page, goto }, agent);
  await agentPage.goto();
  const section = await agentPage.openSection("When it runs");
  // A lone trigger opens with its settings shown.
  await expect(
    section.getByRole("button", { name: `${TRIGGER_NAME} settings` })
  ).toHaveAttribute("aria-expanded", "true");
  const askSwitch = section.getByRole("switch", {
    name: "Ask a person when it can't continue",
  });
  await expect(askSwitch).toHaveAttribute("aria-checked", "true");
  const switchedOff = agentPage.waitForTriggerResponse(
    "PATCH",
    (body) => body?.may_ask_person === false
  );
  await askSwitch.click();
  expect((await switchedOff).status()).toBe(200);
  await expect(askSwitch).toHaveAttribute("aria-checked", "false");

  await fireTicketTrigger(trigger);
  // The stub answers this only when `ask_person` is missing from the offered tools.
  await expect
    .poll(() => lastReply(agent), { timeout: workerTimeout })
    .toMatchObject({
      content: "Nobody to ask.",
      status: "completed",
      approvals: [],
    });
});
