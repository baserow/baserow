import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

/**
 * Dispatches a cell's actions on click and runs the ones the backend hands
 * back. Falls back to the field store where the render context provides no
 * `allFieldsInTable` (functional grid cells, cards).
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
     * Runs the field's actions against this row. The backend rejects a
     * concurrent click for the same field and row, so the local guard only
     * avoids an obvious double fire.
     */
    async dispatchWorkflowActions() {
      if (this.dispatching) {
        return
      }
      this.dispatching = true
      try {
        // The dispatch takes its own broadcast, so `this.row` can change
        // mid-request. Client actions get the row as it was at click time.
        const clickedRow = clone(this.row)
        const { data } = await WorkflowActionService(this.$client).dispatch(
          this.field.id,
          this.row.id
        )
        await this.runClientActions(data?.client_actions || [], clickedRow)
      } catch (error) {
        // A handled error already carries its own message. Anything else, a
        // network failure for instance, still needs a toast of its own.
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
     * Runs the actions the backend hands back for the browser, in the order it
     * returned them. It only sends them when every server side action
     * succeeded, so a failed row action never navigates away.
     */
    async runClientActions(clientActions, row) {
      const fields =
        this.allFieldsInTable?.length > 0
          ? this.allFieldsInTable
          : this.$store.getters['field/getAll']
      for (const workflowAction of clientActions) {
        await this.$registry
          .get('databaseWorkflowActionType', workflowAction.type)
          .execute({
            workflowAction,
            applicationContext: { row, fields },
          })
      }
    },
  },
}
