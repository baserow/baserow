import { getClient } from "../../client";
import { BuilderPage } from "./builderPage";

export class BuilderWorkflowAction {
  constructor(
    public page: BuilderPage,
    public id: number,
    public type: string,
    public element: Element,
    public event: string,
    public properties: Object
  ) {}
}

export async function createBuilderWorkflowAction(
  page: BuilderPage,
  element: Element,
  workflowActionType: string,
  event: string,
  properties: Object = {}
): Promise<BuilderWorkflowAction> {
  const response: any = await getClient(page.builder.workspace.user).post(
    `builder/page/${page.id}/workflow_actions/`,
    {
      type: workflowActionType,
      element_id: element.id,
      event: event,
      ...properties,
    }
  );
  const { id, type, event: eventType, ...rest } = response.data;
  return new BuilderWorkflowAction(
    page,
    response.data.id,
    workflowActionType,
    element,
    eventType,
    rest
  );
}
