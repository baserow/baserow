import { getClient } from "../../client";
import { KumaPanel } from "../../pages/components/kumaPanel";
import { WorkspacePage } from "../../pages/workspacePage";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

const WORDS = 40;
const UNSCRIPTED_ANSWER = "E2E chat";
const TABLE_URL = /\/database\/\d+\/table\/\d+/;

// The e2e stack runs every Kuma run on one Celery process, so runs must not overlap.
test.describe.configure({ mode: "default", timeout: 90_000 });
test.skip(
  process.env.E2E_KUMA_MODEL_STUB !== "yes",
  "Needs Kuma pointed at the model stub in stubs/kuma-model.",
);
test.skip(
  ({ browserName }) => browserName !== "chromium",
  "One browser covers run delivery.",
);

/** "word1 word2 ... word<count>", what the stub answers to `scriptedMessage(count)`. */
function answerOf(count: number): string {
  return Array.from({ length: count }, (_, index) => `word${index + 1}`).join(
    " ",
  );
}

/** Makes the stub build a "Tracker" database with a "Tasks" table, then answer `answerOf(words)`. */
function scriptedMessage(words: number): string {
  return `Build me a tracker. kuma-e2e db=Tracker words=${words}`;
}

/** Matches the answer cut at least as far as `shown`, so a lost or repeated word fails it. */
function answerFrom(shown: string): RegExp {
  const count = shown.trim().split(/\s+/).length;
  const cuts = Array.from({ length: WORDS - count + 1 }, (_, index) =>
    answerOf(count + index),
  );
  return new RegExp(`^\\s*(${cuts.join("|")})\\s*$`);
}

/** The run still answering the workspace's only Kuma chat, or null once it is done. */
async function activeRun(
  workspacePage: WorkspacePage,
): Promise<{ id: string } | null> {
  const client = getClient(workspacePage.user);
  const chatsUrl = `${baserowConfig.PUBLIC_BACKEND_URL}/assistant/chat/`;
  const { data: chats } = await client.get(chatsUrl, {
    params: { workspace_id: workspacePage.workspace.id },
  });
  const { data } = await client.get(
    `${chatsUrl}${chats.results[0].uuid}/messages/`,
  );
  return data.active_run;
}

test("a reload while Kuma answers picks the answer up where it was", async ({
  page,
  workspacePage,
}) => {
  const kuma = new KumaPanel(page);
  const posts: Record<string, unknown>[] = [];
  const statuses: number[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/assistant\/chat\/[^/]+\/messages\/$/.test(request.url())
    ) {
      posts.push(request.postDataJSON());
    }
  });
  page.on("response", (response) => {
    if (
      response.request().method() === "POST" &&
      /\/assistant\/chat\/[^/]+\/messages\/$/.test(response.url())
    ) {
      statuses.push(response.status());
    }
  });
  await workspacePage.goto();
  await kuma.open();
  await kuma.send(scriptedMessage(WORDS));

  for (const word of ["word5", "word15", "word25"]) {
    await expect(kuma.lastAnswer()).toContainText(word, { timeout: 30_000 });
    const shown = (await kuma.lastAnswer().textContent()) ?? "";
    await page.reload();
    await expect(kuma.lastAnswer()).toHaveText(answerFrom(shown), {
      timeout: 30_000,
    });
  }

  await kuma.expectIdle();
  await expect(kuma.answers()).toHaveText([answerOf(WORDS)]);
  expect(posts.filter((body) => "content" in body)).toHaveLength(1);
  expect(posts.filter((body) => "run_id" in body).length).toBeGreaterThan(0);
  expect(
    posts
      .filter((body) => "run_id" in body)
      .every((body) => !("content" in body) && !("ui_context" in body)),
  ).toBe(true);
  expect(statuses.every((status) => status === 200)).toBe(true);
});

test("a failed resume reconnects read-only without another prompt", async ({
  page,
  workspacePage,
}) => {
  const kuma = new KumaPanel(page);
  await workspacePage.goto();
  await kuma.open();
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word3", { timeout: 30_000 });
  let failedResume = false;
  let prompts = 0;
  await page.route("**/assistant/chat/*/messages/", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      if (body.content) prompts += 1;
      if (body.run_id && !failedResume) {
        failedResume = true;
        return route.abort("connectionreset");
      }
    }
    return route.continue();
  });
  await page.reload();
  await kuma.expectIdle();
  await expect(kuma.answers()).toHaveText([answerOf(WORDS)], {
    timeout: 60_000,
  });
  expect(failedResume).toBe(true);
  expect(prompts).toBe(0);
});

test("missing live output recovers the saved answer through durable status", async ({
  page,
  workspacePage,
}) => {
  const kuma = new KumaPanel(page);
  await workspacePage.goto();
  await kuma.open();
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word3", { timeout: 30_000 });
  let resumes = 0;
  let prompts = 0;
  await page.route("**/assistant/chat/*/messages/", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      if (body.content) prompts += 1;
      if (body.run_id) {
        resumes += 1;
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: "\n\n",
        });
      }
    }
    return route.continue();
  });
  await page.reload();
  await expect(kuma.answers()).toHaveText([answerOf(WORDS)], {
    timeout: 60_000,
  });
  await kuma.expectIdle();
  expect(resumes).toBeGreaterThan(0);
  expect(resumes).toBeLessThanOrEqual(3);
  expect(prompts).toBe(0);
});

test("a run keeps going when its tab closes, and a new tab shows the whole answer", async ({
  context,
  page,
  workspacePage,
}) => {
  const kuma = new KumaPanel(page);
  await workspacePage.goto();
  await kuma.open();
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word3", { timeout: 30_000 });
  await page.close();

  await expect
    .poll(() => activeRun(workspacePage), { timeout: 60_000 })
    .toBeNull();

  const reopened = await KumaPanel.inNewTab(
    context,
    workspacePage.getFullUrl(),
  );
  await reopened.openLatestChat();
  await expect(reopened.answers()).toHaveText([answerOf(WORDS)]);
});

test("with two tabs on a chat, only the tab that sent the message follows Kuma to its new table", async ({
  context,
  page,
  workspacePage,
}) => {
  const sender = new KumaPanel(page);
  await workspacePage.goto();
  await sender.open();
  await sender.send("Hello Kuma");
  await expect(sender.lastAnswer()).toHaveText(UNSCRIPTED_ANSWER, {
    timeout: 30_000,
  });
  await sender.expectIdle();

  const watcher = await KumaPanel.inNewTab(context, workspacePage.getFullUrl());
  await watcher.openLatestChat();
  await expect(watcher.answers()).toHaveText([UNSCRIPTED_ANSWER]);
  const watcherUrl = watcher.page.url();

  await sender.send(scriptedMessage(5));

  await expect(page).toHaveURL(TABLE_URL, { timeout: 30_000 });
  await expect(watcher.answers()).toHaveText([UNSCRIPTED_ANSWER, answerOf(5)]);
  await watcher.expectIdle();
  expect(watcher.page.url()).toBe(watcherUrl);
});
