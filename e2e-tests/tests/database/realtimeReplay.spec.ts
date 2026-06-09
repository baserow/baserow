import type { Page } from "@playwright/test";

import { expect, test } from "../baserowTest";
import { WorkspacePage } from "../../pages/workspacePage";
import type { PageConfig } from "../../pages/baserowPage";
import { TablePage } from "../../pages/database/tablePage";
import { createUser, deleteUser } from "../../fixtures/user";
import type { User } from "../../fixtures/user";
import { createWorkspace } from "../../fixtures/workspace";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import type { Table } from "../../fixtures/database/table";
import { createField } from "../../fixtures/database/field";
import { createRows } from "../../fixtures/database/rows";
import { baserowConfig } from "../../playwright.config";
// The frontend handler can't be imported directly from e2e (its top-level
// imports rely on Nuxt-only path aliases), but the protocol constants live
// in a dependency-free module so we can pin against the real source.
import {
  FIRST_CONNECT_CURSOR,
  NO_REPLAY_AVAILABLE,
} from "../../../web-frontend/modules/core/plugins/realtimeProtocol";

const REPLAY_FIELD_NAME = "Replay text";
const REPLAY_MAX_EVENTS_IN_E2E = Number(
  process.env.BASEROW_REALTIME_REPLAY_MAX_EVENTS || 100,
);
const ROW_EVENT_CREATION_CHUNK_SIZE = 10;
const FIRST_RECONNECT_ATTEMPT_MAX_DELAY = 2_200;
const UNKNOWN_EVENT_ID_OFFSET = 1_000_000_000;
type ReplayEventsRequest = {
  type: "replay_events";
  last_seen_id?: number;
};

type ReplayEventsResult = {
  type: "replay_events_result";
  force_refresh?: boolean;
};

type ReceivedRealtimeMessage = {
  type?: string;
  _event_id?: number;
  force_refresh?: boolean;
};

type RealtimeReplayScenario = {
  user: User;
  table: Table;
};

async function setupRealtimeReplayScenario(
  pageConfig: PageConfig,
): Promise<RealtimeReplayScenario> {
  const { page } = pageConfig;

  await installRealtimeWebSocketMonitor(page);

  const user = await createUser();
  const workspace = await createWorkspace(user);
  const database = await createDatabase(
    user,
    uniqueName("realtimeReplayDb"),
    workspace,
  );
  const table = await createTable(
    user,
    uniqueName("realtimeReplayTable"),
    database,
  );
  await createField(user, REPLAY_FIELD_NAME, "text", {}, table);

  const workspacePage = new WorkspacePage(pageConfig, user, workspace);
  await workspacePage.authenticate();

  await page.evaluate(() => {
    localStorage.setItem("baserow.rightSidebarOpen", "false");
  });

  const tablePage = new TablePage(pageConfig);
  await tablePage.goToTable(table);
  await tablePage.waitForLoadingOverlayToDisappear();

  return { user, table };
}

async function withRealtimeReplayScenario(
  pageConfig: PageConfig,
  runTest: (scenario: RealtimeReplayScenario) => Promise<void>,
): Promise<void> {
  let user: User | null = null;

  try {
    const scenario = await setupRealtimeReplayScenario(pageConfig);
    user = scenario.user;
    await runTest(scenario);
  } finally {
    if (user !== null && !process.env.CI) {
      await deleteUser(user);
    }
  }
}

async function installRealtimeWebSocketMonitor(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const OriginalWebSocket = window.WebSocket;
    const realtimeState: {
      sockets: WebSocket[];
      sentMessages: unknown[];
      receivedMessages: unknown[];
      closedSocketCount: number;
    } = {
      sockets: [],
      sentMessages: [],
      receivedMessages: [],
      closedSocketCount: 0,
    };

    function isRealtimeSocket(url: string | URL) {
      return String(url).includes("/ws/core/");
    }

    function rememberJsonMessage(messages: unknown[], data: unknown) {
      if (typeof data !== "string") {
        return;
      }

      try {
        messages.push(JSON.parse(data));
      } catch {
        messages.push(data);
      }
    }

    class MonitoredWebSocket extends OriginalWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        if (protocols === undefined) {
          super(url);
        } else {
          super(url, protocols);
        }

        if (isRealtimeSocket(url)) {
          realtimeState.sockets.push(this);
          this.addEventListener("close", () => {
            realtimeState.closedSocketCount += 1;
          });
          this.addEventListener("message", (event) => {
            rememberJsonMessage(realtimeState.receivedMessages, event.data);
          });
        }
      }

      send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
        if (realtimeState.sockets.includes(this)) {
          rememberJsonMessage(realtimeState.sentMessages, data);
        }

        return super.send(data);
      }
    }

    Object.defineProperty(window, "WebSocket", {
      configurable: true,
      writable: true,
      value: MonitoredWebSocket,
    });

    (window as any).__baserowRealtimeE2E = {
      activeSocketCount() {
        return realtimeState.sockets.filter((socket) =>
          [OriginalWebSocket.CONNECTING, OriginalWebSocket.OPEN].includes(
            socket.readyState,
          ),
        ).length;
      },
      closedSocketCount() {
        return realtimeState.closedSocketCount;
      },
      closeLatestRealtimeSocket() {
        const socket = realtimeState.sockets
          .slice()
          .reverse()
          .find((candidate) =>
            [OriginalWebSocket.CONNECTING, OriginalWebSocket.OPEN].includes(
              candidate.readyState,
            ),
          );

        if (!socket) {
          return false;
        }

        socket.close();
        return true;
      },
      receivedMessages() {
        return realtimeState.receivedMessages;
      },
      sendReplayEventsRequest(lastSeenId: number) {
        const socket = realtimeState.sockets
          .slice()
          .reverse()
          .find((candidate) => candidate.readyState === OriginalWebSocket.OPEN);

        if (!socket) {
          return false;
        }

        socket.send(
          JSON.stringify({
            type: "replay_events",
            last_seen_id: lastSeenId,
          }),
        );
        return true;
      },
      sentMessages() {
        return realtimeState.sentMessages;
      },
      // Opens a throwaway WebSocket, asks the server for the current latest
      // event id via the replay protocol, and returns it. Bypasses the
      // monitored handler so it does not pollute sockets/messages state — the
      // sole purpose is to detect when the async broadcast pipeline (celery)
      // has caught up after a burst of API row creations.
      async queryLatestEventId(wsUrl: string): Promise<number | null> {
        return new Promise((resolve) => {
          let socket: WebSocket;
          try {
            socket = new OriginalWebSocket(wsUrl);
          } catch {
            resolve(null);
            return;
          }
          const timer = setTimeout(() => {
            try { socket.close(); } catch {}
            resolve(null);
          }, 5000);
          socket.addEventListener("message", (event) => {
            try {
              const data = JSON.parse(String(event.data));
              if (data?.type === "authentication" && data.success === true) {
                // ``-1`` is FIRST_CONNECT_CURSOR — the import doesn't
                // survive serialisation into ``addInitScript``.
                socket.send(
                  JSON.stringify({ type: "replay_events", last_seen_id: -1 }),
                );
              } else if (data?.type === "replay_events_result") {
                clearTimeout(timer);
                const latest = typeof data.latest_event_id === "number"
                  ? data.latest_event_id
                  : null;
                try { socket.close(); } catch {}
                resolve(latest);
              }
            } catch {}
          });
          socket.addEventListener("error", () => {
            clearTimeout(timer);
            resolve(null);
          });
        });
      },
    };
  });
}

async function createRow(
  scenario: RealtimeReplayScenario,
  value: string,
): Promise<void> {
  await createRows(scenario.user, scenario.table, [
    {
      [REPLAY_FIELD_NAME]: value,
    },
  ]);
}

async function createManyRowsAsSeparateEvents(
  scenario: RealtimeReplayScenario,
  count: number,
): Promise<void> {
  for (let start = 0; start < count; start += ROW_EVENT_CREATION_CHUNK_SIZE) {
    const chunk = Array.from(
      { length: Math.min(ROW_EVENT_CREATION_CHUNK_SIZE, count - start) },
      (_, index) => uniqueRowValue(`missed-row-${start + index}`),
    );

    await Promise.all(chunk.map((value) => createRow(scenario, value)));
  }
}

// The row-creation API returns as soon as the row is committed, but the
// broadcast that records each event into ws_realtime_events runs in a celery
// task. With celery concurrency=1 in the e2e env, a burst of N row creates
// produces N queued broadcast tasks that drain serially behind the HTTP
// responses. Reconnecting before they drain makes the server see fewer
// recorded events than the test created, breaking force-refresh assertions.
// Also: each row create fans out into multiple realtime events (rows_created
// on the table group, row_history_updated on a per-row group, etc.), so
// counting against a flat ``minimumLatestEventId`` is fragile. Instead, poll
// until the server's latest event id stops growing — the only reliable signal
// that the queue has drained.
async function waitForBroadcastsToBeRecorded(
  page: Page,
  user: User,
): Promise<void> {
  const wsUrl = buildRealtimeWebSocketUrl(user);
  const queryLatest = async () => {
    return await page.evaluate(async (url) => {
      return await (window as any).__baserowRealtimeE2E?.queryLatestEventId(
        url,
      );
    }, wsUrl);
  };

  const STABLE_POLL_INTERVAL_MS = 400;
  const REQUIRED_STABLE_POLLS = 3;
  const MAX_TOTAL_WAIT_MS = 45_000;

  const startedAt = Date.now();
  let previous: number | null = null;
  let stableStreak = 0;
  while (Date.now() - startedAt < MAX_TOTAL_WAIT_MS) {
    const latest = await queryLatest();
    if (latest !== null && previous !== null && latest === previous) {
      stableStreak += 1;
      if (stableStreak >= REQUIRED_STABLE_POLLS) {
        return;
      }
    } else {
      stableStreak = 0;
    }
    previous = latest;
    await page.waitForTimeout(STABLE_POLL_INTERVAL_MS);
  }
  throw new Error(
    "Timed out waiting for the realtime broadcast pipeline to drain: " +
      "the server's latest event id kept growing for the entire wait window",
  );
}

function buildRealtimeWebSocketUrl(user: User): string {
  const backend = new URL(baserowConfig.PUBLIC_BACKEND_URL);
  backend.protocol = backend.protocol === "https:" ? "wss:" : "ws:";
  backend.pathname = "/ws/core/";
  backend.searchParams.set("jwt_token", user.accessToken);
  return backend.toString();
}

async function createVisibleRowAndReturnItsEventId(
  page: Page,
  scenario: RealtimeReplayScenario,
): Promise<number> {
  const liveValue = uniqueRowValue("live-row");

  await createRow(scenario, liveValue);
  await expect(page.getByText(liveValue)).toBeVisible();

  return await expectAnyRealtimeEventIdWasSeen(page);
}

async function disconnectRealtimeAsIfTabWasHiddenAndCountReplayMessages(
  page: Page,
): Promise<{ replayRequestCount: number; replayResultCount: number }> {
  const replayRequestCount = (await getReplayRequests(page)).length;
  const replayResultCount = (await getReplayResults(page)).length;
  const closedSocketCount = await getClosedRealtimeSocketCount(page);

  // The real handler suppresses automatic reconnect while the page is unloading.
  // The test can then create missed events before simulating a tab refocus.
  await page.evaluate(() => {
    window.dispatchEvent(new Event("pagehide"));
  });

  expect(
    await closeLatestRealtimeSocket(page),
    "The test should be able to close the active realtime socket",
  ).toBe(true);

  await expect
    .poll(
      async () => {
        return await getActiveRealtimeSocketCount(page);
      },
      {
        message:
          "The realtime socket should be closed before missed events are created",
      },
    )
    .toBe(0);

  await expect
    .poll(
      async () => {
        return await getClosedRealtimeSocketCount(page);
      },
      {
        message:
          "The app should process the socket close before the test refocuses the tab",
      },
    )
    .toBeGreaterThan(closedSocketCount);

  return { replayRequestCount, replayResultCount };
}

async function refocusTabAndReconnect(page: Page): Promise<void> {
  await page.evaluate(() => {
    document.dispatchEvent(new Event("visibilitychange"));
  });
}

async function expectInitialReplayRequestWasSent(page: Page): Promise<void> {
  await expect
    .poll(
      async () => {
        const replayRequests = await getReplayRequests(page);
        return replayRequests.some(
          (request) => request.last_seen_id === FIRST_CONNECT_CURSOR,
        );
      },
      {
        message:
          "The initial authenticated WebSocket should signal a fresh session via FIRST_CONNECT_CURSOR",
      },
    )
    .toBe(true);
}

async function expectReplayRequestWasSentWithFirstConnectCursor(
  page: Page,
  replayRequestCountBeforeRequest: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const requests = (await getReplayRequests(page)).slice(
          replayRequestCountBeforeRequest,
        );

        return requests.some(
          (request) => request.last_seen_id === FIRST_CONNECT_CURSOR,
        );
      },
      {
        message:
          "The browser should be able to explicitly ask only for a replay baseline via FIRST_CONNECT_CURSOR",
      },
    )
    .toBe(true);
}

async function expectReconnectAskedToReplayFromTheKnownEventId(
  page: Page,
  replayRequestCountBeforeReconnect: number,
  knownEventId: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const reconnectRequests = (await getReplayRequests(page)).slice(
          replayRequestCountBeforeReconnect,
        );

        return reconnectRequests.some(
          (request) =>
            typeof request.last_seen_id === "number" &&
            request.last_seen_id >= knownEventId,
        );
      },
      {
        message:
          "The reconnected WebSocket should ask to replay from the last event the browser saw",
      },
    )
    .toBe(true);
}

async function expectRealtimeStayedDisconnectedUntilTheTabWasVisible(
  page: Page,
  replayRequestCountBeforeReconnect: number,
): Promise<void> {
  await page.waitForTimeout(FIRST_RECONNECT_ATTEMPT_MAX_DELAY);

  expect(
    await getActiveRealtimeSocketCount(page),
    "The realtime handler should not reconnect while the page is hidden",
  ).toBe(0);
  expect(
    (await getReplayRequests(page)).length,
    "The browser should not send replay requests before the page is visible again",
  ).toBe(replayRequestCountBeforeReconnect);

  await expectReconnectWarningsWereNotShown(page);
}

async function expectReconnectWarningsWereNotShown(page: Page): Promise<void> {
  await expect(
    page.getByText("Trying to reestablish real-time updates."),
  ).toHaveCount(0);
  await expect(
    page.getByText("Real-time updates could not be reestablished."),
  ).toHaveCount(0);
}

async function expectReplayResultKeptPageCurrent(
  page: Page,
  replayResultCountBeforeReconnect: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const reconnectResults = (await getReplayResults(page)).slice(
          replayResultCountBeforeReconnect,
        );

        return reconnectResults.some(
          (result) => result.force_refresh === false,
        );
      },
      {
        message:
          "The replay result should say the browser can keep using the page",
      },
    )
    .toBe(true);

  await expectNoReplayResultAskedForRefresh(
    page,
    replayResultCountBeforeReconnect,
  );
  await expectWorkspaceRefreshToastWasNotShown(page);
}

async function expectMissedRowWasReplayedWithoutAskingForRefresh(
  page: Page,
  missedValue: string,
  replayResultCountBeforeReconnect: number,
): Promise<void> {
  await expect(page.getByText(missedValue)).toBeVisible();

  await expectReplayResultKeptPageCurrent(
    page,
    replayResultCountBeforeReconnect,
  );
}

async function expectNoReplayResultAskedForRefresh(
  page: Page,
  replayResultCountBeforeReconnect: number,
): Promise<void> {
  const reconnectResults = (await getReplayResults(page)).slice(
    replayResultCountBeforeReconnect,
  );
  expect(
    reconnectResults,
    "No replay result after reconnect should tell the browser to refresh",
  ).not.toContainEqual(expect.objectContaining({ force_refresh: true }));
}

async function expectReplayResultAskedUserToRefresh(
  page: Page,
  replayResultCountBeforeReconnect: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const reconnectResults = (await getReplayResults(page)).slice(
          replayResultCountBeforeReconnect,
        );

        return reconnectResults.some((result) => result.force_refresh === true);
      },
      {
        message:
          "The replay result should tell the browser to refresh when replay is unsafe",
      },
    )
    .toBe(true);

  await expectWorkspaceRefreshToastWasShown(page);
}

async function expectWorkspaceRefreshToastWasShown(page: Page): Promise<void> {
  // The toast title and body both start with "Too many changes" — match the
  // title element specifically to avoid Playwright's strict-mode locator error.
  await expect(page.locator(".toast__title", { hasText: "Too many changes" })).toBeVisible();
  await expect(page.getByText("Refresh data")).toBeVisible();
}

async function expectWorkspaceRefreshToastWasNotShown(
  page: Page,
): Promise<void> {
  await expect(page.locator(".toast__title", { hasText: "Too many changes" })).toHaveCount(0);
}

async function expectAnyRealtimeEventIdWasSeen(page: Page): Promise<number> {
  await expect
    .poll(
      async () => {
        const eventIds = await getReceivedEventIds(page);
        return eventIds.length;
      },
      {
        message: "A live realtime event should establish the replay baseline",
      },
    )
    .toBeGreaterThan(0);

  const eventIds = await getReceivedEventIds(page);
  return Math.max(...eventIds);
}

async function sendReplayEventsRequest(
  page: Page,
  lastSeenId: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        return await page.evaluate((eventId) => {
          return (
            (window as any).__baserowRealtimeE2E?.sendReplayEventsRequest(
              eventId,
            ) || false
          );
        }, lastSeenId);
      },
      {
        message: "The active realtime socket should accept replay requests",
      },
    )
    .toBe(true);
}

async function getReplayRequests(page: Page): Promise<ReplayEventsRequest[]> {
  return await page.evaluate(() => {
    const messages = ((window as any).__baserowRealtimeE2E?.sentMessages() ||
      []) as any[];
    return messages.filter((message) => message?.type === "replay_events");
  });
}

async function getReplayResults(page: Page): Promise<ReplayEventsResult[]> {
  return await page.evaluate(() => {
    const messages = ((
      window as any
    ).__baserowRealtimeE2E?.receivedMessages() || []) as any[];
    return messages.filter(
      (message) => message?.type === "replay_events_result",
    );
  });
}

async function getReceivedEventIds(page: Page): Promise<number[]> {
  return await page.evaluate(() => {
    const messages = ((
      window as any
    ).__baserowRealtimeE2E?.receivedMessages() || []) as any[];
    return messages
      .map((message: ReceivedRealtimeMessage) => message?._event_id)
      .filter((eventId: unknown) => typeof eventId === "number");
  });
}

async function getActiveRealtimeSocketCount(page: Page): Promise<number> {
  return await page.evaluate(() => {
    return (window as any).__baserowRealtimeE2E?.activeSocketCount() || 0;
  });
}

async function getClosedRealtimeSocketCount(page: Page): Promise<number> {
  return await page.evaluate(() => {
    return (window as any).__baserowRealtimeE2E?.closedSocketCount() || 0;
  });
}

async function closeLatestRealtimeSocket(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    return (
      (window as any).__baserowRealtimeE2E?.closeLatestRealtimeSocket() || false
    );
  });
}

function uniqueRowValue(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function uniqueName(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2)}`;
}

test.describe("realtime replay reliability", () => {
  test.setTimeout(90_000);

  test("replays missed row events after reconnect @fast", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async (scenario) => {
      await expectInitialReplayRequestWasSent(page);
      const knownEventId = await createVisibleRowAndReturnItsEventId(
        page,
        scenario,
      );

      const { replayRequestCount, replayResultCount } =
        await disconnectRealtimeAsIfTabWasHiddenAndCountReplayMessages(page);

      const missedValue = uniqueRowValue("missed-row");
      await createRow(scenario, missedValue);

      await refocusTabAndReconnect(page);
      await expectReconnectAskedToReplayFromTheKnownEventId(
        page,
        replayRequestCount,
        knownEventId,
      );
      await expectMissedRowWasReplayedWithoutAskingForRefresh(
        page,
        missedValue,
        replayResultCount,
      );
    });
  });

  test("keeps the page current when reconnect has nothing to replay @fast", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async (scenario) => {
      await expectInitialReplayRequestWasSent(page);
      const knownEventId = await createVisibleRowAndReturnItsEventId(
        page,
        scenario,
      );

      const { replayRequestCount, replayResultCount } =
        await disconnectRealtimeAsIfTabWasHiddenAndCountReplayMessages(page);

      await refocusTabAndReconnect(page);
      await expectReconnectAskedToReplayFromTheKnownEventId(
        page,
        replayRequestCount,
        knownEventId,
      );
      await expectReplayResultKeptPageCurrent(page, replayResultCount);
    });
  });

  test("reconnects when a hidden page becomes visible again @fast", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async (scenario) => {
      await expectInitialReplayRequestWasSent(page);
      const knownEventId = await createVisibleRowAndReturnItsEventId(
        page,
        scenario,
      );

      const { replayRequestCount, replayResultCount } =
        await disconnectRealtimeAsIfTabWasHiddenAndCountReplayMessages(page);

      await expectRealtimeStayedDisconnectedUntilTheTabWasVisible(
        page,
        replayRequestCount,
      );

      await refocusTabAndReconnect(page);
      await expectReconnectAskedToReplayFromTheKnownEventId(
        page,
        replayRequestCount,
        knownEventId,
      );
      await expectReplayResultKeptPageCurrent(page, replayResultCount);
    });
  });

  test("keeps the page current when explicitly asking for a baseline @fast", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async () => {
      await expectInitialReplayRequestWasSent(page);

      const replayRequestCount = (await getReplayRequests(page)).length;
      const replayResultCount = (await getReplayResults(page)).length;

      await sendReplayEventsRequest(page, FIRST_CONNECT_CURSOR);
      await expectReplayRequestWasSentWithFirstConnectCursor(
        page,
        replayRequestCount,
      );
      await expectReplayResultKeptPageCurrent(page, replayResultCount);
    });
  });

  test("forces refresh when reconnecting with no replay cursor @fast", async ({
    page,
    goto,
  }) => {
    // A client whose previous session ran with replay disabled stores
    // NO_REPLAY_AVAILABLE and sends it on reconnect; the server can't prove
    // what was missed and must ask the user to refresh.
    await withRealtimeReplayScenario({ page, goto }, async () => {
      await expectInitialReplayRequestWasSent(page);

      const replayResultCount = (await getReplayResults(page)).length;

      await sendReplayEventsRequest(page, NO_REPLAY_AVAILABLE);
      await expectReplayResultAskedUserToRefresh(page, replayResultCount);
    });
  });

  test("asks the user to refresh when the browser asks from an unknown event @fast", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async (scenario) => {
      await expectInitialReplayRequestWasSent(page);
      const knownEventId = await createVisibleRowAndReturnItsEventId(
        page,
        scenario,
      );

      const replayResultCount = (await getReplayResults(page)).length;

      await sendReplayEventsRequest(
        page,
        knownEventId + UNKNOWN_EVENT_ID_OFFSET,
      );
      await expectReplayResultAskedUserToRefresh(page, replayResultCount);
    });
  });

  test("asks the user to refresh when too many events were missed", async ({
    page,
    goto,
  }) => {
    await withRealtimeReplayScenario({ page, goto }, async (scenario) => {
      await expectInitialReplayRequestWasSent(page);
      const knownEventId = await createVisibleRowAndReturnItsEventId(
        page,
        scenario,
      );

      const { replayRequestCount, replayResultCount } =
        await disconnectRealtimeAsIfTabWasHiddenAndCountReplayMessages(page);

      await createManyRowsAsSeparateEvents(
        scenario,
        REPLAY_MAX_EVENTS_IN_E2E + 1,
      );
      await waitForBroadcastsToBeRecorded(page, scenario.user);

      await refocusTabAndReconnect(page);
      await expectReconnectAskedToReplayFromTheKnownEventId(
        page,
        replayRequestCount,
        knownEventId,
      );
      await expectReplayResultAskedUserToRefresh(page, replayResultCount);
    });
  });
});
