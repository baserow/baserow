import { getClient } from "../../client";
import { createDatabase } from "../../fixtures/database/database";
import { createField } from "../../fixtures/database/field";
import { createTable } from "../../fixtures/database/table";
import { getStaffUser, getTokenAuth } from "../../fixtures/user";
import { createWorkspace } from "../../fixtures/workspace";
import { TablePage } from "../../pages/database/tablePage";
import { WorkspacePage } from "../../pages/workspacePage";
import { expect, test } from "../baserowTest";

const PROVIDER_TYPES = ["openai", "anthropic", "mistral", "openrouter"];
const MODEL_UNAVAILABLE_ERROR =
  "The selected AI model is disabled or no longer available.";

test.describe.configure({ mode: "serial" });

test("AI field availability stays synchronized while visiting admin settings", async ({
  browserName,
  goto,
  page,
}) => {
  test.skip(
    browserName !== "chromium",
    "Realtime coverage only needs one browser.",
  );
  test.slow();

  const staffUser = process.env.E2E_STAFF_EMAIL
    ? await getTokenAuth(
        process.env.E2E_STAFF_EMAIL,
        process.env.E2E_STAFF_PASSWORD || "testpassword",
      )
    : await getStaffUser();
  const staffClient = getClient(staffUser);
  const modelIdentifier = `e2e-realtime-${Date.now()}`;
  let workspaceId: number | null = null;
  let providerId: number | null = null;
  let modelId: number | null = null;
  let providerCreated = false;
  let providerWasActive = true;

  try {
    const providersResponse = await staffClient.get("ai-providers/");
    const providers = providersResponse.data;
    const configuredTypes = new Set(
      providers.map((provider) => provider.provider_type),
    );
    const availableType = PROVIDER_TYPES.find(
      (providerType) => !configuredTypes.has(providerType),
    );

    if (availableType) {
      const providerResponse = await staffClient.post("ai-providers/", {
        provider_type: availableType,
        api_key: "e2e-secret",
        models: [{ model_identifier: modelIdentifier }],
      });
      providerId = providerResponse.data.id;
      modelId = providerResponse.data.models[0].id;
      providerCreated = true;
    } else {
      const provider = providers.find((candidate) =>
        PROVIDER_TYPES.includes(candidate.provider_type),
      );
      providerId = provider.id;
      providerWasActive = provider.is_active;
      if (!providerWasActive) {
        await staffClient.patch(`ai-providers/${providerId}/`, {
          is_active: true,
        });
      }
      const modelResponse = await staffClient.post(
        `ai-providers/${providerId}/models/`,
        {
          model_identifier: modelIdentifier,
        },
      );
      modelId = modelResponse.data.id;
    }

    const provider = (await staffClient.get("ai-providers/")).data.find(
      (candidate) => candidate.id === providerId,
    );
    const workspace = await createWorkspace(
      staffUser,
      `AI realtime ${Date.now()}`,
    );
    workspaceId = workspace.id;
    const database = await createDatabase(
      staffUser,
      "AI realtime database",
      workspace,
    );
    const table = await createTable(staffUser, "AI realtime table", database, [
      ["Name"],
      ["Project"],
    ]);
    const field = await createField(
      staffUser,
      "AI summary",
      "ai",
      {
        ai_generative_ai_type: provider.provider_type,
        ai_generative_ai_model: modelIdentifier,
        ai_prompt: "'Summarize the project'",
        ai_output_type: "text",
      },
      table,
    );

    const workspacePage = new WorkspacePage(
      { page, goto },
      staffUser,
      workspace,
    );
    await workspacePage.authenticate();
    const tablePage = new TablePage({ page, goto });
    await tablePage.goToTable(table);
    await tablePage.waitForLoadingOverlayToDisappear();
    const tableUrl = new URL(page.url()).pathname;

    const fieldHeader = page.locator(".grid-view__description", {
      has: page.locator(`.grid-view__description-name[title="${field.name}"]`),
    });
    const fieldErrorIcon = fieldHeader.locator(
      ".grid-view__description-icon-error",
    );
    const generateButton = page
      .getByRole("button", { name: "Generate" })
      .first();

    await expect(fieldErrorIcon).toHaveCount(0);
    await expect(generateButton).toBeEnabled();

    await page.evaluate(async () => {
      await (window as any).useNuxtApp().$router.push("/admin/ai-providers");
    });
    await expect(page).toHaveURL(/\/admin\/ai-providers$/);

    await staffClient.patch(`ai-providers/models/${modelId}/`, {
      is_enabled: false,
    });
    await expect
      .poll(() =>
        page.evaluate(
          (fieldId) =>
            (window as any).useNuxtApp().$store.getters["field/get"](fieldId)
              ?.error,
          field.id,
        ),
      )
      .toBe(MODEL_UNAVAILABLE_ERROR);

    await page.evaluate(async (url) => {
      await (window as any).useNuxtApp().$router.push(url);
    }, tableUrl);
    await expect(page).toHaveURL(new RegExp(tableUrl));
    await expect(fieldErrorIcon).toBeVisible();
    await expect(generateButton).toBeDisabled();

    await page.evaluate(async () => {
      await (window as any).useNuxtApp().$router.push("/admin/ai-providers");
    });
    await expect(page).toHaveURL(/\/admin\/ai-providers$/);

    await staffClient.patch(`ai-providers/models/${modelId}/`, {
      is_enabled: true,
    });
    await expect
      .poll(() =>
        page.evaluate(
          (fieldId) =>
            (window as any).useNuxtApp().$store.getters["field/get"](fieldId)
              ?.error,
          field.id,
        ),
      )
      .toBe(null);

    await page.evaluate(async (url) => {
      await (window as any).useNuxtApp().$router.push(url);
    }, tableUrl);
    await expect(page).toHaveURL(new RegExp(tableUrl));
    await expect(fieldErrorIcon).toHaveCount(0);
    await expect(generateButton).toBeEnabled();
  } finally {
    if (modelId !== null && !providerCreated) {
      await staffClient.delete(`ai-providers/models/${modelId}/`);
    }
    if (providerId !== null && providerCreated) {
      await staffClient.delete(`ai-providers/${providerId}/`);
    } else if (providerId !== null && !providerWasActive) {
      await staffClient.patch(`ai-providers/${providerId}/`, {
        is_active: false,
      });
    }
    if (workspaceId !== null) {
      await staffClient.delete(`workspaces/${workspaceId}/`);
    }
  }
});
