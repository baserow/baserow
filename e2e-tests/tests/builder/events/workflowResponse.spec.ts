import { getClient } from "../../../client";
import { createAutomation } from "../../../fixtures/automation/automation";
import type { AutomationNode } from "../../../fixtures/automation/automationNode";
import { createAutomationNode } from "../../../fixtures/automation/automationNode";
import type { AutomationWorkflow } from "../../../fixtures/automation/automationWorkflow";
import { createAutomationWorkflow } from "../../../fixtures/automation/automationWorkflow";
import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { createBuilderWorkflowAction } from "../../../fixtures/builder/builderWorkflowAction";
import { baserowConfig } from "../../../playwright.config";
import { expect, test } from "../../baserowTest";

const raw = (value: string) => ({ formula: value, mode: "raw" });

/** Append and configure a node through the same APIs used by the editor. */
async function addNode(
  workflow: AutomationWorkflow,
  type: string,
  service: Record<string, unknown>,
  reference?: AutomationNode
) {
  const node = await createAutomationNode(
    workflow,
    type,
    reference?.id ?? null
  );
  const { data } = await getClient(workflow.automation.workspace.user).patch(
    `automation/node/${node.id}/`,
    { service: { type, ...service } }
  );
  return { node, service: data.service };
}

/** Wait for the real publish job, failing immediately if publication fails. */
async function publish(workflow: AutomationWorkflow) {
  const client = getClient(workflow.automation.workspace.user);
  const { data: job } = await client.post(
    `automation/workflows/${workflow.id}/publish/async/`,
    {}
  );
  await expect
    .poll(
      async () => {
        const { data } = await client.get(`jobs/${job.id}/`);
        if (data.state === "failed") {
          throw new Error(
            data.human_readable_error || "Workflow publication failed"
          );
        }
        return data.state;
      },
      { timeout: 30000 }
    )
    .toBe("finished");
}

/** Confirm completion, including nodes executed after the first response. */
async function expectSuccessfulRun(workflow: AutomationWorkflow) {
  await expect
    .poll(
      async () => {
        const { data } = await getClient(
          workflow.automation.workspace.user
        ).get(`automation/workflows/${workflow.id}/history/`);
        return data.results.map((run: { status: string }) => run.status);
      },
      { timeout: 15000 }
    )
    .toEqual(["success"]);
}

// Requires the real backend and Celery worker. No dispatches are mocked.
test.describe("Builder workflow responses", () => {
  test.setTimeout(90000);

  for (const caller of ["direct", "parent", "http"] as const) {
    test(`receives a response through ${caller}`, async ({
      context,
      builderPagePage,
      workspacePage,
    }) => {
      const client = getClient(workspacePage.user);
      const automation = await createAutomation(
        "Response scenarios",
        workspacePage.workspace
      );
      const child = await createAutomationWorkflow(
        "Child returns first response",
        automation
      );
      const trigger = await addNode(child, "manual", {
        wait_for_response: true,
        response_timeout_seconds: 5,
      });
      const first = await addNode(
        child,
        "response",
        {
          status_code: raw("201"),
          body_type: "json",
          body: 'from_json(\'{"message":"Created by child","count":3}\')',
          headers: [{ key: "X-Workflow-Result", value: raw("first") }],
        },
        trigger.node
      );
      await addNode(
        child,
        "response",
        {
          status_code: raw("409"),
          body_type: "text",
          body: raw("This second response must be ignored"),
        },
        first.node
      );
      await publish(child);

      let target = child;
      let webhookUrl: string | undefined;
      if (caller !== "direct") {
        target = await createAutomationWorkflow(
          "Parent relays child response",
          automation
        );
        const parentTrigger = await addNode(
          target,
          caller === "http" ? "http_trigger" : "manual",
          {
            wait_for_response: true,
            response_timeout_seconds: 10,
          }
        );
        const startChild = await addNode(
          target,
          "start_workflow",
          {
            workflow_id: child.id,
          },
          parentTrigger.node
        );
        await addNode(
          target,
          "response",
          {
            status_code: `get('previous_node.${startChild.node.id}.status_code')`,
            body_type: "json",
            body: `get('previous_node.${startChild.node.id}.body')`,
            headers: [
              {
                key: "X-Workflow-Result",
                value: `get('previous_node.${startChild.node.id}.headers.X-Workflow-Result')`,
              },
            ],
          },
          startChild.node
        );
        await publish(target);
        // Publishing preserves the HTTP trigger UID for the live webhook.
        webhookUrl = `${baserowConfig.PUBLIC_BACKEND_URL}/api/webhooks/${parentTrigger.service.uid}/`;
      }

      const builderPage = builderPagePage.builderPage;
      const button = await createBuilderElement(builderPage, "button", {
        value: raw("Run response scenario"),
      });
      const action = await createBuilderWorkflowAction(
        builderPage,
        button,
        caller === "http" ? "http_request" : "start_workflow",
        "click",
        {
          service:
            caller === "http"
              ? {
                  type: "http_request",
                  http_method: "POST",
                  url: raw(webhookUrl!),
                  timeout: 15,
                }
              : { type: "start_workflow", workflow_id: target.id },
        }
      );
      // Explicit properties expose the response consumed by the browser action.
      const notification = await createBuilderWorkflowAction(
        builderPage,
        button,
        "notification",
        "click"
      );
      await client.patch(`builder/workflow_action/${notification.id}/`, {
        title: raw("Workflow response received"),
        description: `concat(to_json(get('previous_action.${action.id}.status_code')), ' | ', to_json(get('previous_action.${action.id}.body')), ' | ', get('previous_action.${action.id}.headers.X-Workflow-Result'))`,
      });

      const { data: grant } = await client.post(
        `builder/preview/${builderPagePage.builder.id}/grant/`,
        { path: builderPage.path }
      );
      const preview = await context.newPage();
      await preview.goto(grant.url, { waitUntil: "networkidle" });
      const dispatched = preview.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          response.url().includes(`/${action.id}/dispatch/`)
      );
      await preview
        .getByRole("button", { name: "Run response scenario" })
        .click();
      const result = await dispatched;
      expect(result.status()).toBe(200);
      expect(await result.json()).toMatchObject({
        status_code: 201,
        body: { message: "Created by child", count: 3 },
        headers: { "X-Workflow-Result": "first" },
      });
      await expect(
        preview.getByText("Workflow response received", { exact: true })
      ).toBeVisible();
      await expect(preview.getByText(/^201 \| \{.*\} \| first$/)).toBeVisible();
      await expectSuccessfulRun(child);
      if (target !== child) {
        await expectSuccessfulRun(target);
      }
    });
  }
});
