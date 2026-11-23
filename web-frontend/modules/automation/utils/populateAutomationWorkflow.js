/** Add transient client state to an application child returned by the API. */
export function populateAutomationWorkflow(workflow) {
  return {
    ...workflow,
    nodes: [],
    orderedNodes: [],
    nodeMap: {},
    selectedNodeId: null,
    _: {
      selected: false,
    },
  }
}
