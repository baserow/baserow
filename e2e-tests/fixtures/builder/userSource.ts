import { getClient } from "../../client";
import { Builder } from "./builder";
import { Integration } from "./integration";
import { Table } from "../database/table";
import { Field } from "../database/field";

export class UserSource {
  constructor(
    public id: number,
    public type: string,
    public builder: Builder,
  ) {}
}

/**
 * Creates a Local Baserow user source backed by the given users table, wired to
 * a password auth provider so users can authenticate with email + password. The
 * `roleField` provides each user's role, used by element visibility rules.
 */
export async function createLocalBaserowUserSource(
  builder: Builder,
  integration: Integration,
  table: Table,
  fields: { email: Field; name: Field; role: Field; password: Field },
  name = "Users",
): Promise<UserSource> {
  const response: any = await getClient(builder.workspace.user).post(
    `application/${builder.id}/user-sources/`,
    {
      type: "local_baserow",
      name,
      integration_id: integration.id,
      table_id: table.id,
      email_field_id: fields.email.id,
      name_field_id: fields.name.id,
      role_field_id: fields.role.id,
      auth_providers: [
        {
          type: "local_baserow_password",
          enabled: true,
          password_field_id: fields.password.id,
        },
      ],
    },
  );
  return new UserSource(response.data.id, response.data.type, builder);
}

/**
 * Authenticates a user source user with email + password against the given user
 * source id and returns the JWT pair. Use the returned refresh token as the
 * `user_source_token` cookie to browse the published site as that user.
 */
export async function userSourceTokenAuth(
  userSourceId: number,
  email: string,
  password: string,
): Promise<{ accessToken: string; refreshToken: string }> {
  // Authenticate as a public site visitor would: no Baserow user token. A
  // published user source belongs to no workspace, so a request carrying the
  // builder owner's token is rejected (no permission); an unauthenticated
  // request is the supported path.
  const response: any = await getClient().post(
    `user-source/${userSourceId}/token-auth`,
    { email, password },
  );
  return {
    accessToken: response.data.access_token,
    refreshToken: response.data.refresh_token,
  };
}
