import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Dispatches a button field cell's configured actions when clicked, and runs
 * the ones the backend hands back for the browser. Uses the allFieldsInTable
 * prop where the render context provides it (selected grid cell, row edit
 * modal) and falls back to the field store for contexts that only pass
 * row + field (functional grid cells, cards).
 */
export default {
  data() {
    return {
      dispatching: false,
    }
  },
  computed: {
    hasWorkflowActions() {
      return this.field.has_workflow_actions === true
    },
  },
  methods: {
    /**
     * Runs the field's configured actions against this row. The backend
     * rejects a concurrent click for the same field and row, so the local
     * guard only avoids an obvious double fire.
     */
    async dispatchWorkflowActions() {
      if (this.dispatching) {
        return
      }
      this.dispatching = true
      try {
        const { data } = await WorkflowActionService(this.$client).dispatch(
          this.field.id,
          this.row.id
        )
        await this.runClientActions(data?.client_actions || [])
      } catch (error) {
        // A handled API error already carries its own message. Anything
        // else (e.g. a network failure) still needs its own toast rather
        // than being thrown from an unawaited click handler.
        if (error.handler) {
          notifyIf(error, 'workflowAction')
        } else {
          this.$store.dispatch('toast/error', {
            title: this.$t('buttonField.dispatchErrorTitle'),
            message: this.$t('buttonField.dispatchErrorMessage'),
          })
        }
      } finally {
        this.dispatching = false
      }
    },
    /**
     * Runs the actions the backend does not run itself, in the order it
     * returned them. The response only carries them when the server side
     * actions all succeeded, so a failed row action never navigates away.
     */
    async runClientActions(clientActions) {
      const fields =
        this.allFieldsInTable?.length > 0
          ? this.allFieldsInTable
          : this.$store.getters['field/getAll']
      for (const workflowAction of clientActions) {
        await this.$registry
          .get('databaseWorkflowActionType', workflowAction.type)
          .execute({
            workflowAction,
            applicationContext: { row: this.row, fields },
          })
      }
    },
  },
}
