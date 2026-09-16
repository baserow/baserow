/**
 * Talks to the barrier stub in `e2e-tests/stubs/barrier`, which holds a
 * request from the backend open until a test releases it.
 */

/** The stub as the *backend* reaches it, for the URL an action calls. */
export const BARRIER_STUB_URL = process.env.E2E_BARRIER_STUB_URL;

/**
 * The stub as the tests reach it. Only different from the backend's address
 * when the two sit on different networks, as in `just e2e` and CI.
 */
function controlUrl(): string {
  const url = process.env.E2E_BARRIER_CONTROL_URL ?? BARRIER_STUB_URL;
  if (!url) {
    throw new Error("E2E_BARRIER_STUB_URL is not set, so there is no barrier.");
  }
  return url;
}

async function control(method: string, path: string): Promise<Response> {
  const response = await fetch(`${controlUrl()}/control/${path}`, { method });
  if (!response.ok) {
    throw new Error(
      `The barrier at ${controlUrl()} answered ${response.status} to ${path}.`
    );
  }
  return response;
}

/** How many requests have reached the hold for this key. */
export async function arrivedAt(key: string): Promise<number> {
  const response = await control("GET", `arrived/${encodeURIComponent(key)}`);
  return (await response.json()).count;
}

/** Lets every waiting and later request on this key finish. */
export async function release(key: string): Promise<void> {
  await control("POST", `release/${encodeURIComponent(key)}`);
}

/** Releases everything, so a failed test leaves no request hanging. */
export async function resetBarrier(): Promise<void> {
  await control("POST", "reset");
}
