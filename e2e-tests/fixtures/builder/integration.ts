import { getClient } from "../../client";
import { Builder } from "./builder";

export class Integration {
  constructor(
    public id: number,
    public type: string,
    public builder: Builder
  ) {}
}

export async function createLocalBaserowIntegration(
  builder: Builder,
  name = "Local Baserow"
): Promise<Integration> {
  const response: any = await getClient(builder.workspace.user).post(
    `application/${builder.id}/integrations/`,
    { type: "local_baserow", name }
  );
  return new Integration(response.data.id, response.data.type, builder);
}

/**
 * An SMTP integration on the builder. The password is write-only: the API
 * never returns it, so a test that needs to know it has to remember what it
 * sent here.
 */
export async function createSMTPIntegration(
  builder: Builder,
  options: { name?: string; host?: string; password: string }
): Promise<Integration> {
  const response: any = await getClient(builder.workspace.user).post(
    `application/${builder.id}/integrations/`,
    {
      type: "smtp",
      name: options.name ?? "Mailer",
      host: options.host ?? "smtp.example.com",
      port: 587,
      use_tls: true,
      username: "mailer",
      password: options.password,
    }
  );
  return new Integration(response.data.id, response.data.type, builder);
}

export async function listIntegrations(builder: Builder): Promise<any[]> {
  const response: any = await getClient(builder.workspace.user).get(
    `application/${builder.id}/integrations/`
  );
  return response.data;
}
