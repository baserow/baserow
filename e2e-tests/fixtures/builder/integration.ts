import { getClient } from "../../client";
import { Builder } from "./builder";

export class Integration {
  constructor(
    public id: number,
    public type: string,
    public builder: Builder,
  ) {}
}

export async function createLocalBaserowIntegration(
  builder: Builder,
  name = "Local Baserow",
): Promise<Integration> {
  const response: any = await getClient(builder.workspace.user).post(
    `application/${builder.id}/integrations/`,
    { type: "local_baserow", name },
  );
  return new Integration(response.data.id, response.data.type, builder);
}
