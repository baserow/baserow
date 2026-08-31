import { expect } from "@playwright/test";

/**
 * Reads what the stack actually sent, from the MailHog the e2e environment
 * runs. Without it a send can only be seen in a worker's log, which the tests
 * cannot reach, so an email action could pass while delivering nothing.
 */

export interface CapturedEmail {
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

/** Every message the stack has sent, newest first. */
export async function listEmails(): Promise<CapturedEmail[]> {
  const response = await fetch(`${apiUrl()}/api/v2/messages`);
  if (!response.ok) {
    throw new Error(
      `The mail catcher at ${apiUrl()} answered ${response.status}. Is it ` +
        `running, and is E2E_MAIL_API_URL pointing at it?`,
    );
  }
  const payload: any = await response.json();
  return (payload.items ?? []).map((message: any) => ({
    to: (message.To ?? []).map(
      (recipient: any) => `${recipient.Mailbox}@${recipient.Domain}`,
    ),
    from: headerOf(message, "From"),
    subject: headerOf(message, "Subject"),
    body: message?.Content?.Body ?? "",
  }));
}

export async function deleteAllEmails(): Promise<void> {
  await fetch(`${apiUrl()}/api/v1/messages`, { method: "DELETE" });
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
