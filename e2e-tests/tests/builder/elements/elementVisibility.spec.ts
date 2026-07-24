import { expect, test } from "../../baserowTest";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../../fixtures/licence";
import { createBuilder } from "../../../fixtures/builder/builder";
import { createBuilderPage } from "../../../fixtures/builder/builderPage";
import {
  createBuilderElement,
  updateBuilderElement,
} from "../../../fixtures/builder/builderElement";
import { createLocalBaserowIntegration } from "../../../fixtures/builder/integration";
import {
  createLocalBaserowUserSource,
  userSourceTokenAuth,
} from "../../../fixtures/builder/userSource";
import { publishBuilder } from "../../../fixtures/builder/domain";
import { createDatabase } from "../../../fixtures/database/database";
import { createTable } from "../../../fixtures/database/table";
import {
  createField,
  getFieldsForTable,
} from "../../../fixtures/database/field";
import { listRows, updateRows } from "../../../fixtures/database/rows";
import { baserowConfig } from "../../../playwright.config";

const ROLE = "editor";
const PASSWORD = "supersecret123";

// The five element visibility permutations. Each is a heading whose resolved
// text equals its label, so we can assert which ones render in the DOM.
const ELEMENTS = [
  { label: "E1_ALL", visibility: "all", role_type: "allow_all", roles: [] },
  {
    label: "E2_LOGGED",
    visibility: "logged-in",
    role_type: "allow_all",
    roles: [],
  },
  {
    label: "E3_ALLOW_EDITOR",
    visibility: "logged-in",
    role_type: "disallow_all_except",
    roles: [ROLE],
  },
  {
    label: "E4_DISALLOW_EDITOR",
    visibility: "logged-in",
    role_type: "allow_all_except",
    roles: [ROLE],
  },
  {
    label: "E5_LOGGEDOUT",
    visibility: "not-logged",
    role_type: "allow_all",
    roles: [],
  },
];
const ALL_LABELS = ELEMENTS.map((e) => e.label);

// Which labels each visitor type is expected to see. Notably the authenticated
// visitor with no role must NOT see the same set as the anonymous visitor -
// that collision was the bug this test guards against.
const EXPECTED = {
  anonymous: ["E1_ALL", "E5_LOGGEDOUT"],
  loggedInNoRole: ["E1_ALL", "E2_LOGGED", "E4_DISALLOW_EDITOR"],
  loggedInEditor: ["E1_ALL", "E2_LOGGED", "E3_ALLOW_EDITOR"],
};

test.describe("Builder element visibility on published pages", () => {
  let license: License;

  test.beforeEach(async () => {
    // Local Baserow user sources require an Enterprise license.
    license = await createLicense(ENTERPRISE_LICENSE);
  });

  test.afterEach(async () => {
    await deleteLicense(license);
  });

  test("visitors only see elements matching their visibility permissions @enterprise", async ({
    page,
    workspacePage,
  }) => {
    const { user, workspace } = workspacePage;

    // --- Build the application: a page with the five visibility permutations.
    const builder = await createBuilder("Visibility builder", workspace);
    const builderPage = await createBuilderPage(
      "Visibility",
      "/visibility",
      builder,
    );
    for (const cfg of ELEMENTS) {
      const element = await createBuilderElement(builderPage, "heading", {
        value: `'${cfg.label}'`,
      });
      // role_type/roles are only accepted on update, so configure visibility
      // after creation.
      await updateBuilderElement(element, {
        visibility: cfg.visibility,
        role_type: cfg.role_type,
        roles: cfg.roles,
      });
    }

    // --- Build the user source: a users table with a blank-role and an editor
    // user, wired to a Local Baserow user source with password auth.
    const database = await createDatabase(user, "Users db", workspace);
    const table = await createTable(user, "Users", database, [
      ["Email", "Name", "Role"],
      ["blank@example.com", "Blank", ""],
      ["editor@example.com", "Editor", ROLE],
    ]);
    await createField(user, "Password", "password", {}, table);
    const fields = await getFieldsForTable(user, table);
    const fieldByName = Object.fromEntries(fields.map((f) => [f.name, f]));

    // Passwords are write-only, so set them on the existing rows.
    const rows = await listRows(user, table);
    await updateRows(
      user,
      table,
      rows.map((r) => ({ id: r.id, Password: PASSWORD })),
    );

    const integration = await createLocalBaserowIntegration(builder);
    const userSource = await createLocalBaserowUserSource(
      builder,
      integration,
      table,
      {
        email: fieldByName.Email,
        name: fieldByName.Name,
        role: fieldByName.Role,
        password: fieldByName.Password,
      },
    );

    // --- Publish. The published copy filters elements by visibility.
    const published = await publishBuilder(
      builder,
      `e2e-visibility-${userSource.id}-${Date.now()}.example.com`,
    );

    // --- Authenticate each user source user against the published user source.
    const blankAuth = await userSourceTokenAuth(
      published.userSourceId,
      "blank@example.com",
      PASSWORD,
    );
    const editorAuth = await userSourceTokenAuth(
      published.userSourceId,
      "editor@example.com",
      PASSWORD,
    );

    const previewUrl = `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}${published.previewPath()}`;
    const frontendHost = new URL(baserowConfig.PUBLIC_WEB_FRONTEND_URL)
      .hostname;
    const cookieName = `${baserowConfig.BASEROW_FRONTEND_COOKIE_PREFIX}user_source_token`;

    // Visit the published page as a given visitor and assert exactly which of
    // the five headings render. `refreshToken` null means an anonymous visit.
    const assertVisibleFor = async (
      refreshToken: string | null,
      expectedLabels: string[],
    ) => {
      // Reset to a clean visitor: no Baserow session, no user source token.
      await page.context().clearCookies();
      if (refreshToken) {
        await page.context().addCookies([
          {
            name: cookieName,
            value: refreshToken,
            domain: frontendHost,
            path: "/",
          },
        ]);
      }

      await page.goto(previewUrl, { waitUntil: "networkidle" });

      // E1_ALL is visible to everyone, so wait for it to confirm the page rendered.
      await expect(
        page.locator(".ab-heading", { hasText: "E1_ALL" }),
      ).toBeVisible();

      for (const label of ALL_LABELS) {
        const heading = page.locator(".ab-heading", { hasText: label });
        if (expectedLabels.includes(label)) {
          await expect(heading, `${label} should be visible`).toBeVisible();
        } else {
          await expect(heading, `${label} should be hidden`).toHaveCount(0);
        }
      }
    };

    // Order matters: the anonymous visit runs first on purpose. The original bug
    // was that an anonymous request and a logged-in visitor with no role shared a
    // server-side cache entry, so the first visitor's element set was served to
    // both. Visiting anonymously first is what poisons that shared entry, so if
    // the fix regresses the logged-in-no-role assertion below will fail.
    await assertVisibleFor(null, EXPECTED.anonymous);
    await assertVisibleFor(blankAuth.refreshToken, EXPECTED.loggedInNoRole);
    await assertVisibleFor(editorAuth.refreshToken, EXPECTED.loggedInEditor);
  });
});
