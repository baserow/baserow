import { Page, Route } from "@playwright/test";

export interface RouteOptions {
  /**
   * Only intercept requests with this HTTP method (e.g. "POST", "PATCH").
   * Requests with other methods continue normally.
   * If omitted, all methods are intercepted.
   */
  method?: string;
}

export interface PausedRequest {
  /** Let the intercepted request proceed normally. */
  release: () => void;
  /** Fulfill the intercepted request with HTTP 500 instead of continuing it. */
  fail: () => void;
  intercepted: Promise<void>;
}

/**
 * Arms a one-shot route intercept that fulfills the NEXT matching request
 * with HTTP 500. Returns a promise that resolves once the 500 has been
 * delivered, so callers can `await` it before asserting rollback state.
 *
 * Pass `{ method: "POST" }` to only intercept POST requests and let GETs
 * through - important for the flat grid which fires background GETs.
 *
 * Usage:
 *   const failed = failNextRequest(page, `**\/rows\/table\/${id}\/`, { method: "POST" })
 *   await grid.addRow()
 *   await failed
 *   await grid.expectRowCount(1)   // optimistic row was rolled back
 */
export function failNextRequest(
  page: Page,
  urlPattern: string,
  options: RouteOptions = {},
): Promise<void> {
  return new Promise((resolve) => {
    const handler = async (route: Route) => {
      if (options.method && route.request().method() !== options.method) {
        // Wrong method - let it through and keep the handler registered
        await route.continue();
        return;
      }
      // Correct method (or no method filter) - fail it and unregister.
      // Use a Baserow-structured body so hasBaserowAPIError() returns true and
      // the standard error toast fires.
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERROR_E2E_FORCED_FAILURE",
          detail: "Forced e2e failure.",
        }),
      });
      await page.unroute(urlPattern, handler);
      resolve();
    };
    page.route(urlPattern, handler);
  });
}

export async function pauseNextRequestWithSignal(
  page: Page,
  urlPattern: string,
  options: RouteOptions = {},
): Promise<PausedRequest> {
  let release!: () => void;
  let fail!: () => void;
  let releaseGate!: () => void;
  let markIntercepted!: () => void;
  let handler!: (route: Route) => Promise<void>;
  let interceptedResolved = false;
  let released = false;
  let failMode = false;
  let routed = true;
  const gate = new Promise<void>((r) => {
    releaseGate = r;
  });
  const intercepted = new Promise<void>((r) => {
    markIntercepted = r;
  });

  const unrouteOnce = async () => {
    if (!routed) {
      return;
    }
    routed = false;
    await page.unroute(urlPattern, handler);
  };

  release = () => {
    if (released) {
      return;
    }
    released = true;
    failMode = false;
    releaseGate();
  };

  fail = () => {
    if (released) {
      return;
    }
    released = true;
    failMode = true;
    releaseGate();
  };

  handler = async (route: Route) => {
    if (options.method && route.request().method() !== options.method) {
      await route.continue();
      return;
    }
    if (interceptedResolved) {
      await route.continue();
      return;
    }
    interceptedResolved = true;
    markIntercepted();
    await gate;
    if (failMode) {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERROR_E2E_FORCED_FAILURE",
          detail: "Forced e2e failure.",
        }),
      });
    } else {
      await route.continue();
    }
    await unrouteOnce();
  };

  await page.route(urlPattern, handler);

  return { release, fail, intercepted };
}
