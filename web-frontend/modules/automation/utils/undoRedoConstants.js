// The different types of undo/redo scopes available for the automations module.
export const AUTOMATION_ACTION_SCOPES = {
  workflow(workflowId) {
    return {
      workflow: workflowId,
    }
  },
}
