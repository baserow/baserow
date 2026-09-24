<template>
  <component
    :is="actionType.form"
    ref="form"
    :key="action.type"
    v-bind="actionType.getFormProps({ workflowAction: action, database })"
    :default-values="action"
    @values-changed="$emit('values-changed', $event)"
  />
</template>

<script>
/**
 * One action's form, with a formula context of its own. The data explorer
 * offers an action only what precedes it in the list, so each form needs to
 * know which action it belongs to, and `provide` is per component rather than
 * per loop iteration.
 */
export default {
  name: 'ButtonFieldActionForm',
  inject: {
    parentFormulaContext: { from: 'databaseFormulaContext', default: null },
  },
  provide() {
    // Delegates to the parent rather than copying it. Spreading would read the
    // parent's getters here, making the actions list a dependency of the
    // provided object itself, so every mounted formula input would rebuild its
    // explorer on each keystroke. Reading through the traps keeps that
    // tracking where it belongs: in whatever computed does the reading.
    const parent = () => this.parentFormulaContext || {}
    return {
      databaseFormulaContext: new Proxy(
        {},
        {
          get: (target, property) =>
            property === 'workflowAction' ? this.action : parent()[property],
          has: (target, property) =>
            property === 'workflowAction' || property in parent(),
          ownKeys: () => [
            ...new Set([...Reflect.ownKeys(parent()), 'workflowAction']),
          ],
          getOwnPropertyDescriptor: (target, property) => ({
            enumerable: true,
            configurable: true,
            value:
              property === 'workflowAction' ? this.action : parent()[property],
          }),
        }
      ),
    }
  },
  props: {
    action: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  emits: ['values-changed'],
  computed: {
    actionType() {
      return this.$registry.get('databaseWorkflowActionType', this.action.type)
    },
  },
  methods: {
    /** Whether the action's own form accepts what it holds. */
    isValid() {
      return this.$refs.form?.isFormValid?.(true) ?? true
    },
  },
}
</script>
