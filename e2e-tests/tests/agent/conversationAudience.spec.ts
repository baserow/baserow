import { randomUUID } from "crypto";
import type { Page } from "@playwright/test";
import { getClient } from "../../client";
import {
  createAgentIdentity,
  createSupportAgent,
  setAgentRunIdentity,
} from "../../fixtures/agent/agent";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { Workspace } from "../../fixtures/workspace";
import { AgentPage } from "../../pages/agent/agentPage";
import { expect, test } from "../baserowTest";

const modelHost = process.env.E2E_AGENT_MODEL_HOST;
test.skip(
  !modelHost,
  "Needs the E2E model stub reachable by the agent worker."
);
// Trigger delivery and model replies share the E2E stack's single Celery worker.
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
    const agent = await createSupportAgent(workspace);
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

test("a support team can approve privately after the author leaves", async ({
  page,
  goto,
  workspacePage,
}) => {
  const { workspace, user } = workspacePage;
  const license = await createLicense(ENTERPRISE_LICENSE);
  const members: User[] = [];
  try {
    for (let i = 0; i < 3; i++) {
      const member = await createUser();
      members.push(member);
    }
    await joinWorkspace(workspace, members, "EDITOR");
    const client = getClient(user);
    const { data: team } = await client.post(
      `teams/workspace/${workspace.id}/`,
      { name: "Support team" }
    );
    for (const member of members) {
      await client.post(`teams/${team.id}/subjects/`, {
        subject_user_email: member.email,
        subject_type: "auth.User",
      });
    }
    const agent = await createSupportAgent(workspace);
    await setAgentRunIdentity(
      agent,
      await createAgentIdentity("Support assistant", workspace, "BUILDER")
    );
    await client.patch(`agent/${agent.id}/configuration/`, {
      allowed_tools: ["create_database"],
      ask_first_tools: ["create_database"],
    });
    const agentPage = new AgentPage({ page, goto }, agent);
    await agentPage.goto();
    const section = await agentPage.openSection("Permissions");
    const approval = section
      .locator(".control")
      .filter({ hasText: "Who can approve tool calls" });
    await approval.locator(".dropdown__selected").click();
    await approval
      .getByText("Specific users or teams", { exact: true })
      .click();
    const modal = page.locator(".modal__box:visible");
    await modal.locator(".dropdown__selected").click();
    await modal
      .locator(".select__item-link")
      .filter({ hasText: "Support team" })
      .click();
    await expect(
      modal.locator(".field-permission-subjects__list")
    ).toContainText("Support team");
    await modal.locator(".modal__close").click();
    await expect(
      approval.getByText("Manage people and teams (1)")
    ).toBeVisible();

    const title = "Create a support database.";
    await send(page, title);
    await page.getByRole("button", { name: "Ask for approval" }).click();
    for (const member of members.slice(0, 2)) {
      await modal.locator(".dropdown__selected").click();
      await page
        .locator(".select__item-link:visible")
        .filter({ hasText: member.name })
        .click();
    }
    await modal.getByRole("button", { name: "Ask for approval" }).click();
    await expect(page.locator(".agent-audience")).toContainText(
      members[1].name
    );
    await expect(page.locator(".agent-audience")).toContainText("Private");
    await conversationAction(page, title, "Delete");
    await modal.getByRole("button", { name: "Delete for me" }).click();
    await expect(
      page.locator(".agent-conversations__row", { hasText: title })
    ).toHaveCount(0);
    expect(await conversations(members[1], agent.id)).toMatchObject([
      { title, shared: false },
    ]);
    expect(await conversations(members[2], agent.id)).toEqual([]);

    await agentPage.authenticate(members[0]);
    await agentPage.goto();
    await page
      .locator(".agent-conversations__item", { hasText: title })
      .click();
    await expect(page.locator(".agent-audience")).toContainText("Private");
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(page.locator(".agent-chat")).toContainText(
      "The support database is ready.",
      { timeout: workerTimeout }
    );
    const { data: applications } = await client.get(
      `applications/workspace/${workspace.id}/`
    );
    expect(applications).toContainEqual(
      expect.objectContaining({ type: "database", name: "Support" })
    );
  } finally {
    for (const member of members) await deleteUser(member);
    await deleteLicense(license);
  }
});

test("a triggered conversation appears shared and a teammate can continue it once allowed", async ({
  page,
  goto,
  workspacePage,
}) => {
  const { workspace, user } = workspacePage;
  const license = await createLicense(ENTERPRISE_LICENSE);
  try {
    const member = await createUser();
    try {
      await joinWorkspace(workspace, [member], "EDITOR");
      const agent = await createSupportAgent(workspace);
      const agentPage = new AgentPage({ page, goto }, agent);
      await agentPage.goto();
      const section = await agentPage.openSection("Permissions");
      const continuing = section.locator(".control").filter({
        hasText: "Who can continue triggered conversations",
      });
      await expect(continuing.locator(".dropdown__selected")).toContainText(
        "Nobody"
      );
      const saved = page.waitForResponse(
        (response) =>
          response.url().endsWith(`agent/${agent.id}/permissions/continue/`) &&
          response.request().method() === "PUT"
      );
      await continuing.locator(".dropdown__selected").click();
      await continuing.getByText("Editors and higher", { exact: true }).click();
      expect((await saved).ok()).toBe(true);
      const { data: trigger } = await getClient(user).post(
        `agent/${agent.id}/triggers/`,
        {
          type: "http_trigger",
          name: "Ticket received",
          message: "get('trigger.body.subject')",
        }
      );
      const title = "Shipping address change";
      await getClient().post(`webhooks/${trigger.service.uid}/`, {
        subject: title,
      });
      await expect
        .poll(() => conversations(member, agent.id), { timeout: workerTimeout })
        .toMatchObject([{ title, started_by_trigger: true, shared: true }]);
      await agentPage.authenticate(member);
      await agentPage.goto();
      const row = page.locator(".agent-conversations__row", { hasText: title });
      await expect(row.locator(".agent-conversations__private")).toHaveCount(0);
      await row.locator(".agent-conversations__item").click();
      await expect(page.locator(".agent-chat")).toContainText("E2E chat", {
        timeout: workerTimeout,
      });
      const followup = "Please confirm the shipping address.";
      await send(page, followup);
      const [conversation] = await conversations(user, agent.id);
      await expect
        .poll(
          async () => {
            const { data } = await getClient(user).get(
              `agent/${agent.id}/conversations/${conversation.uuid}/messages/`
            );
            return data.results.slice(-2);
          },
          { timeout: workerTimeout }
        )
        .toMatchObject([
          { role: "user", content: followup, sender: { name: member.name } },
          { role: "assistant", content: "E2E chat", status: "completed" },
        ]);
    } finally {
      await deleteUser(member);
    }
  } finally {
    await deleteLicense(license);
  }
});
