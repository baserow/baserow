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
  release: () => void;
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
      // Use a Baserow-structured body so the client-side ErrorHandler fires the
      // toast notification. An empty {} body is parsed as an object by axios,
      // causing hasBaserowAPIError() to return false and the toast to be suppressed.
      await page.unroute(urlPattern, handler);
      await route.fulfill({ status: 500, body: "{}" });
      resolve();
    };
    page.route(urlPattern, handler);
  });
}

/**
 * Arms a route intercept that PAUSES matching requests until the returned
 * `release` function is called.
 *
 * Pass `{ method: "POST" }` to only pause POST requests.
 *
 * Usage:
 *   const release = await pauseNextRequest(page, pattern, { method: "POST" })
 *   await grid.addRow()
 *   // Optimistic state visible - network paused
 *   await grid.expectRowCount(2)
 *   release()
 *   await grid.expectRowCount(2)   // BE confirmed
 */
export async function pauseNextRequest(
  page: Page,
  urlPattern: string,
  options: RouteOptions = {},
): Promise<() => void> {
  const paused = await pauseNextRequestWithSignal(page, urlPattern, options);
  return paused.release;
}

export async function pauseNextRequestWithSignal(
  page: Page,
  urlPattern: string,
  options: RouteOptions = {},
): Promise<PausedRequest> {
  let release!: () => void;
  let releaseGate!: () => void;
  let markIntercepted!: () => void;
  let handler!: (route: Route) => Promise<void>;
  let interceptedResolved = false;
  let released = false;
  const gate = new Promise<void>((r) => {
    releaseGate = r;
  });
  const intercepted = new Promise<void>((r) => {
    markIntercepted = r;
  });

  release = () => {
    if (released) {
      return;
    }
    released = true;
    releaseGate();
    void page.unroute(urlPattern, handler);
  };

  handler = async (route: Route) => {
    if (options.method && route.request().method() !== options.method) {
      await route.continue();
      return;
    }
    if (!interceptedResolved) {
      interceptedResolved = true;
      markIntercepted();
    }
    await gate;
    await route.continue();
  };

  await page.route(urlPattern, handler);

  return { release, intercepted };
}
