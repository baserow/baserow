import { Page } from "@playwright/test";
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
  "Needs Kuma pointed at the model stub in stubs/kuma-model."
);
test.skip(
  ({ browserName }) => browserName !== "chromium",
  "One browser covers run delivery."
);

/** "word1 word2 ... word<count>", what the stub answers to `scriptedMessage(count)`. */
function answerOf(count: number): string {
  return Array.from({ length: count }, (_, index) => `word${index + 1}`).join(
    " "
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
    answerOf(count + index)
  );
  return new RegExp(`^\\s*(${cuts.join("|")})\\s*$`);
}

/** The run still answering the workspace's only Kuma chat, or null once it is done. */
async function activeRun(
  workspacePage: WorkspacePage
): Promise<{ id: string } | null> {
  const client = getClient(workspacePage.user);
  const chatsUrl = `${baserowConfig.PUBLIC_BACKEND_URL}/assistant/chat/`;
  const { data: chats } = await client.get(chatsUrl, {
    params: { workspace_id: workspacePage.workspace.id },
  });
  const { data } = await client.get(
    `${chatsUrl}${chats.results[0].uuid}/messages/`
  );
  return data.active_run;
}

async function openKuma(
  page: Page,
  workspacePage: WorkspacePage
): Promise<KumaPanel> {
  const kuma = new KumaPanel(page);
  await workspacePage.goto();
  await kuma.open();
  return kuma;
}

/** Counts prompts sent to Kuma; resumes post to the same URL without content. */
function countPrompts(page: Page): () => number {
  let prompts = 0;
  page.on("request", (request) => {
    if (
      /\/assistant\/chat\/[^/]+\/messages\/$/.test(request.url()) &&
      request.postDataJSON()?.content
    ) {
      prompts += 1;
    }
  });
  return () => prompts;
}

test("a reload while Kuma answers picks the answer up where it was", async ({
  page,
  workspacePage,
}) => {
  const prompts = countPrompts(page);
  const kuma = await openKuma(page, workspacePage);
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word5", { timeout: 30_000 });
  const shown = (await kuma.lastAnswer().textContent()) ?? "";

  await page.reload();
  await expect(kuma.lastAnswer()).toHaveText(answerFrom(shown), {
    timeout: 30_000,
  });
  // The saved answer is whole, so only a live resume can show a partial one.
  expect(await kuma.lastAnswer().textContent()).not.toContain(`word${WORDS}`);

  await kuma.expectIdle();
  await expect(kuma.answers()).toHaveText([answerOf(WORDS)]);
  expect(prompts()).toBe(1);
});

test("a reply whose resumed stream ends early shows the saved answer from its status", async ({
  page,
  workspacePage,
}) => {
  const prompts = countPrompts(page);
  const kuma = await openKuma(page, workspacePage);
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word3", { timeout: 30_000 });
  let resumes = 0;
  await page.route("**/assistant/chat/*/messages/", async (route) => {
    if (route.request().postDataJSON()?.run_id) {
      resumes += 1;
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "\n\n",
      });
    }
    return route.continue();
  });
  await page.reload();
  await expect(kuma.answers()).toHaveText([answerOf(WORDS)], {
    timeout: 60_000,
  });
  await kuma.expectIdle();
  expect(resumes).toBeGreaterThan(0);
  expect(prompts()).toBe(1);
});

test("a run keeps going when its tab closes, and a new tab shows the whole answer", async ({
  context,
  page,
  workspacePage,
}) => {
  const kuma = await openKuma(page, workspacePage);
  await kuma.send(scriptedMessage(WORDS));
  await expect(kuma.lastAnswer()).toContainText("word3", { timeout: 30_000 });
  await page.close();

  await expect
    .poll(() => activeRun(workspacePage), { timeout: 60_000 })
    .toBeNull();

  const reopened = await KumaPanel.inNewTab(
    context,
    workspacePage.getFullUrl()
  );
  await reopened.openLatestChat();
  await expect(reopened.answers()).toHaveText([answerOf(WORDS)]);
});

test("with two tabs on a chat, only the tab that sent the message follows Kuma to its new table", async ({
  context,
  page,
  workspacePage,
}) => {
  const sender = await openKuma(page, workspacePage);
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
