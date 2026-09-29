import {
  createSMTPIntegration,
  listIntegrations,
} from "../../fixtures/builder/integration";
import { expect, test } from "../baserowTest";

/**
 * The SMTP password is write-only: it can be set and overwritten, but the API
 * never returns it to anyone, the creator included.
 *
 * These cover the seam between the two halves of that rule, which unit tests
 * on either side cannot see. The form omits an untouched password from the
 * request; the backend reads an omitted password as "keep what is stored". If
 * either side changes its mind about what an untouched field looks like, a
 * save that has nothing to do with the password silently destroys it, and
 * nothing tells the user.
 */

const PASSWORD = "e2e-top-secret";

/** Open the builder application's Integrations settings. */
async function openIntegrationSettings(page, builderName: string) {
  // The application's own row. Scope to its direct `.tree__action` child: the
  // pages nested underneath carry a `.tree__options` of their own.
  const sidebarRow = page
    .locator("li.tree__item", { hasText: builderName })
    .locator("> .tree__action");
  await sidebarRow.hover();

  // The Context self-hides when it doesn't fit the viewport, and the first
  // click can land before hydration settles, so retry until the item shows.
  const settingsItem = page.locator(
    '.context__menu-item-link:visible:has-text("Settings")'
  );
  await expect(async () => {
    await sidebarRow.locator(".tree__options").click();
    await expect(settingsItem).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15000 });
  await settingsItem.click();

  await page
    .locator(".modal-sidebar__nav-link", { hasText: "Integrations" })
    .click();
  await expect(
    page.locator(".box__title", { hasText: "Integrations" })
  ).toBeVisible();
}

/** Open the edit modal of the integration with the given name. */
async function openIntegrationEditModal(page, name: string) {
  const row = page.locator(".integration-settings__integration", {
    hasText: name,
  });
  await row
    .locator(".integration-settings__integration-actions .button-icon")
    .first()
    .click();

  const modal = page.locator(".modal__box:visible", {
    hasText: "Edit integration",
  });
  await expect(modal).toBeVisible();
  return modal;
}

test.describe("Write-only integration secrets", () => {
  test("the password is never sent to the browser, and a rename keeps it", async ({
    page,
    builderPagePage,
  }) => {
    const builder = builderPagePage.builder;
    await createSMTPIntegration(builder, {
      name: "Mailer",
      password: PASSWORD,
    });

    // Every response the browser receives, from the moment it loads the
    // builder. A single one carrying the password is the bug this guards.
    const leaked: string[] = [];
    // Playwright does not await a listener's promise, so every body read has
    // to be collected and awaited before asserting, or a leaking response
    // still in flight would slip past and the test would pass on nothing.
    const reads: Promise<void>[] = [];
    page.on("response", (response) => {
      if (!response.url().includes("/api/")) return;
      reads.push(
        response
          .text()
          .then((body) => {
            if (body.includes(PASSWORD)) leaked.push(response.url());
          })
          // Redirects and responses without a body cannot leak anything.
          .catch(() => {})
      );
    });

    await builderPagePage.goto();
    await openIntegrationSettings(page, builder.name);
    const modal = await openIntegrationEditModal(page, "Mailer");

    // The field renders empty, and says so rather than looking unset.
    const password = modal.getByPlaceholder(
      "Leave blank to keep the saved password"
    );
    await expect(password).toHaveValue("");
    await expect(
      modal.getByText("A password is saved. Leave blank to keep it.")
    ).toBeVisible();

    // A save that has nothing to do with the password.
    await modal
      .getByPlaceholder("Enter integration name...")
      .fill("Renamed mailer");
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(modal).toBeHidden();

    const [integration] = await listIntegrations(builder);
    expect(integration.name).toBe("Renamed mailer");
    // The password survived the save, and the API still refuses to show it.
    expect(integration.has_password).toBe(true);
    expect(integration).not.toHaveProperty("password");

    await Promise.all(reads);
    expect(leaked, "the password was sent to the browser").toEqual([]);
  });

  test("changing the host without retyping the password is refused", async ({
    page,
    builderPagePage,
  }) => {
    const builder = builderPagePage.builder;
    await createSMTPIntegration(builder, {
      name: "Mailer",
      host: "smtp.example.com",
      password: PASSWORD,
    });

    await builderPagePage.goto();
    await openIntegrationSettings(page, builder.name);
    const modal = await openIntegrationEditModal(page, "Mailer");

    await modal
      .getByPlaceholder("smtp.gmail.com")
      .fill("smtp.attacker.example");
    await modal.getByRole("button", { name: "Save" }).click();

    await expect(modal.getByText("Credential required")).toBeVisible();
    await expect(
      modal.getByText(
        "Enter the credential again to change where this integration connects."
      )
    ).toBeVisible();

    // Nothing was written: the host is unchanged and the password is intact.
    const [integration] = await listIntegrations(builder);
    expect(integration.host).toBe("smtp.example.com");
    expect(integration.has_password).toBe(true);
  });

  test("retyping the password lets the host change go through", async ({
    page,
    builderPagePage,
  }) => {
    const builder = builderPagePage.builder;
    await createSMTPIntegration(builder, {
      name: "Mailer",
      host: "smtp.example.com",
      password: PASSWORD,
    });

    await builderPagePage.goto();
    await openIntegrationSettings(page, builder.name);
    const modal = await openIntegrationEditModal(page, "Mailer");

    await modal.getByPlaceholder("smtp.gmail.com").fill("smtp.newhost.example");
    await modal
      .getByPlaceholder("Leave blank to keep the saved password")
      .fill("a-new-secret");
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(modal).toBeHidden();

    const [integration] = await listIntegrations(builder);
    expect(integration.host).toBe("smtp.newhost.example");
    expect(integration.has_password).toBe(true);
    expect(integration).not.toHaveProperty("password");
  });
});
