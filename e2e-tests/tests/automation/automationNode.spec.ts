import { Page } from "@playwright/test";

import { expect, test } from "../baserowTest";

import { createAutomationNode } from "../../fixtures/automation/automationNode";
import { AutomationWorkflowPage } from "../../pages/automation/automationWorkflowPage";

/**
 * Opens the workflow page and waits until the requested node has rendered.
 * A single retry covers stale first renders after API fixture setup.
 */
async function gotoAndExpectNode(
  automationWorkflowPage: AutomationWorkflowPage,
  page: Page,
  nodeName: string
) {
  await automationWorkflowPage.goto();

  const getNode = () => page.getByRole("heading", {
    name: nodeName,
    level: 1,
  });

  try {
    await expect(getNode()).toBeVisible({ timeout: 5000 });
  } catch {
    await automationWorkflowPage.goto();
    await expect(getNode()).toBeVisible();
  }

  return getNode();
}

/**
 * Captures the next realtime websocket and waits until it is authenticated.
 * API mutations made before this point can race ahead of the page subscription.
 */
async function waitForNextRealtimeAuthentication(page: Page) {
  const websocket = await page.waitForEvent("websocket", { timeout: 10000 });

  await websocket.waitForEvent("framereceived", {
    timeout: 10000,
    predicate: ({ payload }) => {
      const text = typeof payload === "string" ? payload : payload.toString();

      try {
        const data = JSON.parse(text);
        return data.type === "authentication" && data.success === true;
      } catch {
        return false;
      }
    },
  });

  return websocket;
}

/**
 * Waits for a specific realtime event on an already authenticated websocket.
 * The predicate scopes the event to the workflow/node created by this test.
 */
async function waitForRealtimeEvent(
  websocket: any,
  eventType: string,
  predicate: (data: any) => boolean
) {
  await websocket.waitForEvent("framereceived", {
    timeout: 20000,
    predicate: ({ payload }: any) => {
      const text = typeof payload === "string" ? payload : payload.toString();

      try {
        const data = JSON.parse(text);
        return data.type === eventType && predicate(data);
      } catch {
        return false;
      }
    },
  });
}

/**
 * Opens an empty workflow, verifies the canvas reached its empty state, and
 * returns the authenticated websocket used for later realtime assertions.
 */
async function gotoAndExpectEmptyWorkflow(
  automationWorkflowPage: AutomationWorkflowPage,
  page: Page
) {
  const gotoAndAssert = async (timeout = 5000) => {
    const realtimeAuthentication = waitForNextRealtimeAuthentication(page);
    await automationWorkflowPage.goto();

    try {
      await expect(page.getByText("Choose an event...")).toBeVisible({
        timeout,
      });
      return await realtimeAuthentication;
    } catch (error) {
      await realtimeAuthentication.catch(() => null);
      throw error;
    }
  };

  try {
    return await gotoAndAssert();
  } catch {
    return await gotoAndAssert(10000);
  }
}

test.describe("Automation node test suite", () => {
  let trigger;
  test.beforeEach(async ({ automationWorkflowPage, page }) => {
    trigger = await createAutomationNode(
      automationWorkflowPage.automationWorkflow,
      "periodic"
    );

    await gotoAndExpectNode(automationWorkflowPage, page, "Periodic trigger");
  });

  test("Can create an automation node", async ({ page }) => {
    const createNodeButton = page.getByRole("button", {
      name: "Create automation node",
    });
    await createNodeButton.click();

    const rowsCreatedOption = page.getByText("Create a row");
    await expect(rowsCreatedOption).toBeVisible();
    await rowsCreatedOption.click();

    const nodeDiv = page.getByRole("heading", {
      name: "Create a row",
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();
  });

  test("Can delete an automation node", async ({
    page,
    automationWorkflowPage,
  }) => {
    await createAutomationNode(
      automationWorkflowPage.automationWorkflow,
      "local_baserow_create_row",
      trigger.id,
      "south",
      ""
    );
    const nodeDiv = await gotoAndExpectNode(
      automationWorkflowPage,
      page,
      "Create a row"
    );

    // Let's select the node
    await nodeDiv.click();

    await page.locator(".vue-flow__controls-fitview").click();

    const nodeMenuButton = page
      .locator(".workflow-node-content--selected")
      .getByRole("button", { name: "Node options" });
    await nodeMenuButton.click();

    const deleteNodeButton = page.getByRole("button", { name: "Delete" });
    await deleteNodeButton.waitFor({ state: "visible" });
    deleteNodeButton.click();

    await expect(nodeDiv).not.toBeVisible();
  });
});

test.describe("Automation node realtime test suite", () => {
  test.setTimeout(45000);

  test("Can render an API-created trigger in an already-open workflow", async ({
    automationWorkflowPage,
    page,
  }) => {
    const realtimeWebSocket = await gotoAndExpectEmptyWorkflow(
      automationWorkflowPage,
      page
    );

    const workflowId = automationWorkflowPage.automationWorkflow.id;
    const nodeCreated = waitForRealtimeEvent(
      realtimeWebSocket,
      "automation_node_created",
      (data) => data.node.workflow === workflowId
    );
    const workflowUpdated = waitForRealtimeEvent(
      realtimeWebSocket,
      "automation_workflow_updated",
      (data) => data.workflow.id === workflowId
    );

    await createAutomationNode(
      automationWorkflowPage.automationWorkflow,
      "periodic"
    );
    await Promise.all([nodeCreated, workflowUpdated]);

    const triggerNode = page.locator(".workflow-node-content").filter({
      has: page.getByRole("heading", {
        name: "Periodic trigger",
        level: 1,
      }),
    });

    await expect(triggerNode).toBeVisible();
    await expect(triggerNode.getByText("Configure")).toBeVisible();
  });
});
