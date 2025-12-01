import { getClient } from "../../client";
import { BuilderPage } from "./builderPage";

export class BuilderElement {
  constructor(
    public page: BuilderPage,
    public id: number,
    public type: string,
    public properties: Object
  ) {}
}

export async function createBuilderElement(
  page: BuilderPage,
  elementType: string,
  properties: Object = {}
): Promise<BuilderElement> {
  const response: any = await getClient(page.builder.workspace.user).post(
    `builder/page/${page.id}/elements/`,
    {
      page_id: page.id,
      type: elementType,
      ...properties,
    }
  );
  const { id, type, ...rest } = response.data;
  return new BuilderElement(page, response.data.id, elementType, rest);
}
