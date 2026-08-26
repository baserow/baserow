import { reactive } from 'vue'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

// Keyed by field and row rather than kept per component. The grid swaps an
// unselected cell for its own component on the first click, and that remount
// would drop a flag held in `data`, taking the loading state and the double
// click guard with it.
const dispatchesInFlight = reactive(new Set())

/**
 * Dispatches a cell's actions on click and runs the ones the backend hands
 * back. Falls back to the field store where the render context provides no
 * `allFieldsInTable` (functional grid cells, cards).
 */
export default {
  computed: {
    hasWorkflowActions() {
      return this.field.has_workflow_actions === true
    },
    dispatchKey() {
      return `${this.field.id}:${this.row.id}`
    },
    dispatching() {
      return dispatchesInFlight.has(this.dispatchKey)
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
      // Captured up front so the release below cannot miss it if the cell is
      // handed a different row while the request is in flight.
      const key = this.dispatchKey
      dispatchesInFlight.add(key)
      try {
        // The dispatch takes its own broadcast, so `this.row` can change
        // mid-request. Client actions get the row as it was at click time.
        const clickedRow = clone(this.row)
        const { data } = await WorkflowActionService(this.$client).dispatch(
          this.field.id,
          this.row.id
        )
        await this.runClientActions(
          data?.client_actions || [],
          clickedRow,
          this.previousActionResults(data)
        )
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
        dispatchesInFlight.delete(key)
      }
    },
    /**
     * What the server side actions returned, for a client action to reference.
     * The result is keyed by field name, so the ids it came with travel with
     * it: the browser has no other way to map a `field_<id>` in a formula onto
     * a row of a table that is not this one.
     */
    previousActionResults(data) {
      return Object.fromEntries(
        (data?.results || []).map((result) => [
          String(result.workflow_action_id),
          {
            data: result.data,
            fieldNames: result.field_names || {},
            order: result.order,
            position: result.position,
          },
        ])
      )
    },
    /**
     * The results of the actions that ran before this one. Client actions run
     * last whatever their place in the list, so without this a reference to an
     * action ordered after them would resolve here while the dispatch would
     * have refused it.
     */
    resultsBefore(previousActionResults, workflowAction) {
      // Two actions can carry the same `order`, which the dispatch then breaks
      // by id, so `position` is what really says which ran first. `order` is
      // the fallback for a backend that sends no position.
      const byPosition =
        workflowAction.position !== undefined &&
        workflowAction.position !== null
      const place = byPosition ? workflowAction.position : workflowAction.order
      if (place === undefined || place === null) {
        return previousActionResults
      }
      return Object.fromEntries(
        Object.entries(previousActionResults).filter(([, result]) => {
          const resultPlace = byPosition ? result.position : result.order
          return resultPlace === undefined || resultPlace === null
            ? true
            : resultPlace < place
        })
      )
    },
    /**
     * Runs the actions the backend hands back for the browser, in the order it
     * returned them. It only sends them when every server side action
     * succeeded, so a failed row action never navigates away.
     */
    async runClientActions(clientActions, row, previousActionResults = {}) {
      const fields =
        this.allFieldsInTable?.length > 0
          ? this.allFieldsInTable
          : this.$store.getters['field/getAll']
      for (const workflowAction of clientActions) {
        await this.$registry
          .get('databaseWorkflowActionType', workflowAction.type)
          .execute({
            workflowAction,
            applicationContext: {
              row,
              fields,
              previousActionResults: this.resultsBefore(
                previousActionResults,
                workflowAction
              ),
            },
          })
      }
    },
  },
}
