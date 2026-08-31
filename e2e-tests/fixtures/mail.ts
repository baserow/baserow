import { expect } from "@playwright/test";

/**
 * Reads what the stack actually sent, from the MailHog the e2e environment
 * runs. Without it a send can only be seen in a worker's log, which the tests
 * cannot reach, so an email action could pass while delivering nothing.
 */

export interface CapturedEmail {
  id: string;
  to: string[];
  from: string;
  subject: string;
  body: string;
}

function apiUrl(): string {
  return process.env.E2E_MAIL_API_URL ?? "http://localhost:8075";
}

function headerOf(message: any, name: string): string {
  const values = message?.Content?.Headers?.[name];
  return Array.isArray(values) ? values.join(", ") : (values ?? "");
}

// MailHog answers a page at a time, and a long lived catcher also holds every
// signup and notification mail the rest of the suite sent, so the default page
// is not wide enough to find a message by subject.
const MESSAGE_PAGE_SIZE = 200;

/** Every message the stack has sent, newest first. */
export async function listEmails(): Promise<CapturedEmail[]> {
  const response = await fetch(
    `${apiUrl()}/api/v2/messages?limit=${MESSAGE_PAGE_SIZE}`,
  );
  if (!response.ok) {
    throw new Error(
      `The mail catcher at ${apiUrl()} answered ${response.status}. Is it ` +
        `running, and is E2E_MAIL_API_URL pointing at it?`,
    );
  }
  const payload: any = await response.json();
  return (payload.items ?? []).map((message: any) => ({
    id: message.ID,
    to: (message.To ?? []).map(
      (recipient: any) => `${recipient.Mailbox}@${recipient.Domain}`,
    ),
    from: headerOf(message, "From"),
    subject: headerOf(message, "Subject"),
    body: message?.Content?.Body ?? "",
  }));
}

/**
 * Drops one message, so a test leaves the catcher as it found it.
 *
 * Scoped to a single id on purpose. Emptying the catcher would take messages
 * that are not this test's: the workers run in parallel and read the same one,
 * and against a dev stack it is the developer's own captured mail.
 */
export async function deleteEmail(id: string): Promise<void> {
  const response = await fetch(`${apiUrl()}/api/v1/messages/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(
      `The mail catcher at ${apiUrl()} answered ${response.status} when asked ` +
        `to drop message ${id}.`,
    );
  }
}

/**
 * Waits for a message with the given subject. Sending goes through Celery, so
 * it does not land the moment the click returns.
 */
export async function waitForEmail(subject: string): Promise<CapturedEmail> {
  let found: CapturedEmail | undefined;

  await expect(async () => {
    const emails = await listEmails();
    found = emails.find((email) => email.subject === subject);
    expect(found, `no email with subject "${subject}" arrived`).toBeTruthy();
  }).toPass({ timeout: 20_000 });

  return found as CapturedEmail;
}
