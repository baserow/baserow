export const TriggerNodeTypeMixin = (Base) =>
  class extends Base {
    isWorkflowTrigger = true
  }

export const ActionNodeTypeMixin = (Base) =>
  class extends Base {
    isWorkflowAction = true
  }
