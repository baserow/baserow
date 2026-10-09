import { createHash, randomBytes } from "crypto";
import { APIRequestContext } from "@playwright/test";
import { expect, test } from "../baserowTest";
import { baserowConfig } from "../../playwright.config";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { createWorkspace, Workspace } from "../../fixtures/workspace";

const backendUrl = baserowConfig.PUBLIC_BACKEND_URL.replace(/\/$/, "");
const frontendUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL.replace(/\/$/, "");
const mcpUrl = `${backendUrl}/mcp`;
// Nothing listens here: page.route answers the callback, like a local MCP client.
const callbackOrigin = "http://127.0.0.1:33419";
const redirectUri = `${callbackOrigin}/callback`;

let user: User;
let workspace: Workspace;

test.beforeEach(async () => {
  user = await createUser();
  workspace = await createWorkspace(user);
});

test.afterEach(async () => {
  // In CI the database is thrown away, and the first user is the admin.
  if (!process.env.CI) {
    await deleteUser(user);
  }
});

function base64url(buffer: Buffer): string {
  return buffer.toString("base64url");
}

async function callMcp(
  request: APIRequestContext,
  token: string,
  id: number,
  method: string,
  params: object = {}
) {
  const response = await request.post(mcpUrl, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json, text/event-stream",
      "Content-Type": "application/json",
    },
    data: { jsonrpc: "2.0", id, method, params },
  });
  const text = await response.text();
  // The answer is either plain JSON or a single server-sent event.
  const dataLine = text.split("\n").find((line) => line.startsWith("data:"));
  const body = dataLine
    ? JSON.parse(dataLine.slice("data:".length))
    : text
      ? JSON.parse(text)
      : null;
  return { status: response.status(), body };
}

test("An MCP client connects with OAuth and is disconnected in settings", async ({
  page,
  goto,
  request,
}) => {
  // Two full page loads plus the token and MCP round trips.
  test.setTimeout(90 * 1000);
  const metadataResponse = await request.get(
    `${backendUrl}/.well-known/oauth-authorization-server`
  );
  test.skip(
    metadataResponse.status() !== 200,
    "BASEROW_MCP_OAUTH_ENABLED is off on the backend under test"
  );
  const metadata = await metadataResponse.json();

  const clientName = `E2E MCP client ${randomBytes(4).toString("hex")}`;
  const registration = await request.post(`${backendUrl}/oauth/register/`, {
    data: {
      client_name: clientName,
      redirect_uris: [redirectUri],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
    },
  });
  expect(registration.status()).toBe(201);
  const clientId = (await registration.json()).client_id;

  const verifier = base64url(randomBytes(48));
  const challenge = base64url(createHash("sha256").update(verifier).digest());
  const state = base64url(randomBytes(12));
  const authorizeUrl =
    `${backendUrl}/oauth/authorize/?` +
    new URLSearchParams({
      response_type: "code",
      client_id: clientId,
      redirect_uri: redirectUri,
      code_challenge: challenge,
      code_challenge_method: "S256",
      scope: "mcp",
      state,
      resource: mcpUrl,
    }).toString();

  let callbackUrl = null as URL | null;
  await page.route(`${callbackOrigin}/**`, async (route) => {
    callbackUrl = new URL(route.request().url());
    await route.fulfill({
      contentType: "text/html",
      body: "<p>You can close this window.</p>",
    });
  });

  await page.goto(`${frontendUrl}?token=${user.refreshToken}`);
  // The backend validates the request and redirects to the consent page.
  await goto(authorizeUrl, { waitUntil: "hydration" });

  await expect(page.locator('[data-test="mcp-authorize-title"]')).toHaveText(
    `Connect ${clientName}`
  );
  await expect(
    page.locator('[data-test="mcp-authorize-unverified"]')
  ).toContainText("Not verified");
  const deleteRows = page.locator(
    '[data-test="mcp-authorize-tool-delete_rows"]'
  );
  await expect(deleteRows).toHaveClass(/checkbox--checked/);
  await deleteRows.click();
  await expect(deleteRows).not.toHaveClass(/checkbox--checked/);
  await page.locator('[data-test="mcp-authorize-allow"]').click();

  await expect.poll(() => callbackUrl?.pathname).toBe("/callback");
  const params = callbackUrl!.searchParams;
  expect(params.get("state")).toBe(state);
  expect(params.get("iss")).toBe(metadata.issuer);
  const code = params.get("code");
  expect(code).toBeTruthy();

  const tokenResponse = await request.post(`${backendUrl}/oauth/token/`, {
    form: {
      grant_type: "authorization_code",
      code: code!,
      client_id: clientId,
      code_verifier: verifier,
      redirect_uri: redirectUri,
      resource: mcpUrl,
    },
  });
  expect(tokenResponse.status()).toBe(200);
  const accessToken = (await tokenResponse.json()).access_token;

  const initialize = await callMcp(request, accessToken, 1, "initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "e2e", version: "1.0.0" },
  });
  expect(initialize.status).toBe(200);
  expect(initialize.body.result.serverInfo).toBeTruthy();

  const toolsList = await callMcp(request, accessToken, 2, "tools/list");
  expect(toolsList.status).toBe(200);
  const toolNames = toolsList.body.result.tools.map(
    (tool: { name: string }) => tool.name
  );
  expect(toolNames).toContain("list_databases");
  expect(toolNames).not.toContain("delete_rows");

  await goto(`${frontendUrl}/workspace/${workspace.id}`, {
    waitUntil: "hydration",
  });
  await page.locator(".sidebar__workspaces-selector-link").click();
  await page.locator(".context__menu").getByText("My settings").click();
  await page.locator(".modal-sidebar__nav").getByText("MCP server").click();

  const connection = page
    .locator(".mcp-oauth-connections__item")
    .filter({ hasText: clientName });
  await expect(connection).toBeVisible();
  const disconnect = connection.locator('[data-test="mcp-oauth-disconnect"]');
  await disconnect.click();
  await expect(disconnect).toHaveText("Click again to disconnect");
  await disconnect.click();
  await expect(connection).toHaveCount(0);

  const revoked = await callMcp(request, accessToken, 3, "tools/list");
  expect(revoked.status).toBe(401);
});
