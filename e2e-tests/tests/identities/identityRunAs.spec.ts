import { getClient } from "../../client";
import { createAgent } from "../../fixtures/agent/agent";
import { AgentPage } from "../../pages/agent/agentPage";
import { expect, test } from "../baserowTest";

// The section's copy, from web-frontend/modules/agent/locales/en.json.
const COPY = {
  section: "Workspace access",
  noAccess: "No workspace access",
};

test("an agent runs as an identity of its workspace, never as a person", async ({
  page,
  goto,
  workspacePage,
}) => {
  const { user, workspace } = workspacePage;
  const client = getClient(user);
  const identity = (
    await client.post(`identities/workspace/${workspace.id}/`, {
      name: "Ops runner",
    })
  ).data;
  const agent = await createAgent("Run as agent", workspace);
  const agentPage = new AgentPage({ page, goto }, agent);
  await agentPage.goto();

  const section = await agentPage.openSection(COPY.section);
  await section.locator(".dropdown__selected").click();
  const options = page.locator(".select__item:visible");
  await expect(options.getByText(identity.name, { exact: true })).toBeVisible();
  await expect(options.getByText(COPY.noAccess, { exact: true })).toBeVisible();
  // People can't be picked: an agent acts only as an identity.
  await expect(options).toHaveCount(2);

  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/agent/${agent.id}/configuration/`)
  );
  await options.getByText(identity.name, { exact: true }).click();
  expect((await saved).status()).toBe(200);
  const configuration = (await client.get(`agent/${agent.id}/configuration/`))
    .data;
  expect(configuration.run_as).toMatchObject({
    type: "auth.User",
    id: identity.id,
    name: identity.name,
    status: "active",
  });

  // Trashing the identity takes the agent's workspace access away.
  await client.delete(`identities/${identity.id}/`);
  await agentPage.goto();
  const reopened = await agentPage.openSection(COPY.section);
  await expect(
    reopened.getByText(`${identity.name} is in the trash`, { exact: false })
  ).toBeVisible();
  const afterTrash = (await client.get(`agent/${agent.id}/configuration/`))
    .data;
  expect(afterTrash.run_as.status).toBe("trashed");
});
