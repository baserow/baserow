import { getClient } from "../../client";
import { Builder } from "./builder";
import { User } from "../user";

export class BuilderPage {
  constructor(
    public id: number,
    public name: string,
    public path: string,
    public builder: Builder
  ) {}
}

export async function createBuilderPage(
  pageName: string,
  path: string,
  builder: Builder
): Promise<BuilderPage> {
  const response: any = await getClient(builder.workspace.user).post(
    `builder/${builder.id}/pages/`,
    {
      name: pageName,
      path,
      path_params: [],
      query_params: [],
    }
  );
  return new BuilderPage(
    response.data.id,
    response.data.name,
    response.data.path,
    builder
  );
}
