import { reactive } from 'vue'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

// Keyed by field and row rather than kept per component. The grid swaps an
// unselected cell for its own component on the first click, and that remount
// would drop a flag held in `data`, taking the loading state and the double
// click guard with it.
const dispatchesInFlight = reactive(new Set())

const DISPATCH_OPERATION = 'database.table.field.workflow_action.dispatch'

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
    /**
     * An action writes to a field or table that is in the trash or gone, so
     * the click is sure to fail. Worked out server side, where the trash is.
     */
    requiresReconfiguration() {
      return this.field.requires_reconfiguration === true
    },
    /**
     * The row select modal's grid is the one place that hands no workspace,
     * so there it is found through the field's table. A miss gives `null`,
     * which the permission check answers with `false`: a disabled button
     * saying the user may not click.
     */
    fieldWorkspaceId() {
      if (this.workspaceId != null) {
        return this.workspaceId
      }
      const database = this.$store.getters['application/getAll'].find(
        (application) =>
          application.tables?.some((table) => table.id === this.field.table_id)
      )
      return database?.workspace?.id ?? null
    },
    /**
     * Whether this user may click at all, which is a lower bar than editing
     * the row and a higher one than reading it. The backend refuses the click
     * either way, so this only stops the button offering one.
     */
    canDispatch() {
      return this.$hasPermission(
        DISPATCH_OPERATION,
        this.field,
        this.fieldWorkspaceId
      )
    },
    canClick() {
      return this.hasWorkflowActions && this.canDispatch
    },
    /** A disabled button fires no mouse events, so its wrapper shows this. */
    disabledReason() {
      return this.hasWorkflowActions && !this.canDispatch
        ? this.$t('buttonField.noPermission')
        : null
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
      const newTab = this.openNewTab()
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
          this.previousActionResults(data),
          newTab
        )
      } catch (error) {
        // The shared handler stays quiet on a 429, so a refused click would
        // otherwise look like a click that did nothing.
        if (error.handler?.isTooManyRequests?.()) {
          this.$store.dispatch('toast/error', {
            title: this.$t('buttonField.rateLimitedTitle'),
            message: this.$t('buttonField.rateLimitedMessage'),
          })
        } else if (error.handler) {
          // A handled error already carries its own message. Anything else, a
          // network failure for instance, still needs a toast of its own.
          notifyIf(error, 'workflowAction')
        } else {
          this.$store.dispatch('toast/error', {
            title: this.$t('buttonField.dispatchErrorTitle'),
            message: this.$t('buttonField.dispatchErrorMessage'),
          })
        }
      } finally {
        dispatchesInFlight.delete(key)
        // Still here when the dispatch failed or no action navigated it.
        newTab?.discard()
      }
    },
    /**
     * Opens the tab a new tab action will navigate, while the click still
     * counts as one. Safari blocks a `window.open` made once the dispatch
     * request has returned, and says nothing about it.
     *
     * @returns {Object|null} `take()` hands the tab to the one action that
     *   navigates it, `discard()` closes it if none did.
     */
    openNewTab() {
      if (this.field.opens_new_tab !== true) {
        return null
      }
      // Not `noopener`: that makes `window.open` return null, leaving nothing
      // to navigate. Cut the link by hand instead.
      let tab = window.open('', '_blank')
      if (!tab) {
        return null
      }
      tab.opener = null
      return {
        take() {
          // Closed by the user while the dispatch ran: nothing to navigate.
          const taken = tab?.closed ? null : tab
          tab = null
          return taken
        },
        discard() {
          tab?.close()
          tab = null
        },
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
    async runClientActions(
      clientActions,
      row,
      previousActionResults = {},
      newTab = null
    ) {
      const fields =
        this.allFieldsInTable?.length > 0
          ? this.allFieldsInTable
          : this.$store.getters['field/getAll']
      for (const workflowAction of clientActions) {
        const ran = await this.$registry
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
              newTab,
            },
          })
        // The server cannot tell whether the browser opened the URL, so this
        // is the one button event sent from the client.
        try {
          this.$posthog?.capture('button_field_client_action', {
            field_id: this.field.id,
            workflow_action_type: workflowAction.type,
            ran: ran !== false,
          })
        } catch {
          // Analytics must never stop the actions after this one.
        }
        // An action that could not run stops the ones after it, the way a
        // failed server action stops the sequence. Carrying on would navigate
        // away from the message this one just raised.
        if (ran === false) {
          break
        }
      }
    },
  },
}
