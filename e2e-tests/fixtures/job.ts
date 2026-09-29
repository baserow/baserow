import { AxiosInstance } from "axios";

/**
 * Polls an async job until it finishes and returns its final payload, or
 * throws with the job's own error when it fails or runs out of time.
 */
export async function waitForJob(
  client: AxiosInstance,
  jobId: number,
  description: string,
  { timeoutMs = 30_000, intervalMs = 500 } = {}
): Promise<any> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const poll: any = await client.get(`jobs/${jobId}/`);
    if (poll.data.state === "failed") {
      throw new Error(
        `${description} failed: ${poll.data.human_readable_error || ""}`
      );
    }
    if (poll.data.state === "finished") {
      return poll.data;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`${description} did not finish in time`);
}
