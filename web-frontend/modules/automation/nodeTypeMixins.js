export const TriggerNodeTypeMixin = (Base) =>
  class extends Base {
    isTrigger = true

    /**
     * Triggers cannot be moved around, so we return true here.
     * @returns {boolean} - Whether the node can be moved.
     */
    get isFixed() {
      return true
    }

    /**
     * Triggers cannot be deleted, so by default we return an error message.
     * @param workflow - the workflow that contains the node.
     * @param node - the node that is being deleted.
     * @returns {string} - The error message to display when
     *  trying to delete a trigger node.
     */
    getDeleteErrorMessage({ workflow, node }) {
      return this.app.$i18n.t('nodeType.triggerDeletionError')
    }

    isDuplicable({ workflow, node }) {
      return false
    }
  }

export const ActionNodeTypeMixin = (Base) =>
  class extends Base {
    isWorkflowAction = true
    // Whether the node shows the error handling form (fail or retry). A type
    // whose dispatch can only fail the same way again sets it to false, like
    // the backend's `has_error_policy`.
    hasErrorPolicy = true
  }

export const UtilityNodeTypeMixin = (Base) =>
  class extends Base {
    isUtilityNode = true
  }

export const ContainerNodeTypeMixin = (Base) =>
  class extends Base {
    isContainer = true
  }
