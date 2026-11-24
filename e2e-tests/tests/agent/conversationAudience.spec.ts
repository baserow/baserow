import { randomUUID } from "crypto";
import type { Page } from "@playwright/test";
import { getClient } from "../../client";
import { createAgent } from "../../fixtures/agent/agent";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { Workspace } from "../../fixtures/workspace";
import { AgentPage } from "../../pages/agent/agentPage";
import { expect, test } from "../baserowTest";

const modelHost = process.env.E2E_AGENT_MODEL_HOST;
test.skip(
  !modelHost,
  "Needs the E2E model stub reachable by the agent worker."
);
// Model replies share the E2E stack's single Celery worker.
const workerTimeout = 60_000;
test.describe.configure({ timeout: 180_000 });

async function joinWorkspace(
  workspace: Workspace,
  members: User[],
  permissions: string
) {
  const client = getClient(workspace.user);
  const base = "workspaces/invitation-links/";
  const { data: link } = await client.post(
    base + `workspace/${workspace.id}/`,
    {
      name: "Support reviewers",
      permissions,
    }
  );
  try {
    for (const member of members) {
      await getClient(member).post(base + `slug/${link.slug}/join/`);
    }
  } finally {
    await client.delete(base + `${link.id}/`);
  }
}

async function supportAgent(workspace: Workspace) {
  const client = getClient(workspace.user);
  await client.post(`ai-providers/?workspace_id=${workspace.id}`, {
    provider_type: "ollama",
    extra_settings: { host: modelHost },
    models: [{ model_identifier: "kuma-e2e", feature_types: ["ai_agent"] }],
  });
  const agent = await createAgent("Customer support", workspace);
  await client.patch(`agent/${agent.id}/configuration/`, {
    instructions: "Help customers with support requests.",
    provider_type: "ollama",
    model_identifier: "kuma-e2e",
  });
  return agent;
}

async function send(page: Page, message: string) {
  const input = page.getByPlaceholder("Send a message to Customer support…");
  await input.fill(message);
  await input.press("Enter");
}

async function conversationAction(page: Page, title: string, action: string) {
  const row = page.locator(".agent-conversations__row", { hasText: title });
  await row.hover();
  await row.getByRole("button", { name: "Conversation options" }).click();
  await page
    .locator(".context__menu-item-link:visible")
    .getByText(action, { exact: true })
    .click();
}

async function conversations(user: User, agentId: number) {
  const { data } = await getClient(user).get(`agent/${agentId}/conversations/`);
  return data.results;
}

test("sharing requires confirmation and lets members continue until a manager deletes it", async ({
  page,
  goto,
  workspacePage,
}) => {
  const { workspace } = workspacePage;
  const member = await createUser();
  try {
    await joinWorkspace(workspace, [member], "MEMBER");
    const agent = await supportAgent(workspace);
    const agentPage = new AgentPage({ page, goto }, agent);
    await agentPage.goto();
    const title = "Where is my shipment?";
    await send(page, title);
    await expect(page.locator(".agent-chat")).toContainText("E2E chat", {
      timeout: workerTimeout,
    });
    const row = page.locator(".agent-conversations__row", { hasText: title });
    const lock = row.locator(".agent-conversations__private");
    await expect(lock).toBeVisible();
    await conversationAction(page, title, "Share");
    const modal = page.locator(".modal__box:visible");
    await expect(modal).toContainText("Sharing can’t be undone");
    await modal.getByRole("button", { name: "Cancel" }).click();
    expect(await conversations(member, agent.id)).toEqual([]);

    await conversationAction(page, title, "Share");
    const shareResponse = page.waitForResponse((response) =>
      response.url().endsWith("/share/")
    );
    await modal.getByRole("button", { name: "Share", exact: true }).click();
    expect((await shareResponse).ok()).toBe(true);
    await expect(lock).toHaveCount(0);
    const [shared] = await conversations(member, agent.id);
    expect(shared).toMatchObject({
      title,
      shared: true,
      started_by_trigger: false,
    });

    const followup = "It was due yesterday.";
    await getClient(member).post(
      `agent/${agent.id}/conversations/${shared.uuid}/messages/`,
      { uuid: randomUUID(), content: followup }
    );
    const memberMessage = page.locator(".chat-message", { hasText: followup });
    await expect(memberMessage).toContainText(member.name);
    await expect(
      page.locator(".chat-message", { hasText: "E2E chat" })
    ).toHaveCount(2, { timeout: workerTimeout });

    await conversationAction(page, title, "Delete");
    await expect(row).toHaveCount(0);
    expect(await conversations(member, agent.id)).toEqual([]);
  } finally {
    await deleteUser(member);
  }
});
