export const TriggerNodeTypeMixin = (Base) =>
  class extends Base {
    isTrigger = true
  }

export const ActionNodeTypeMixin = (Base) =>
  class extends Base {
    isWorkflowAction = true
  }
