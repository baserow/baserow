import {
  encodeUrlWhitespace,
  resolveButtonUrl,
} from '@baserow/modules/database/utils/buttonField'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Computes the {url, label} value of a button field cell, and dispatches the
 * field's configured actions when clicked. Uses the allFieldsInTable prop
 * where the render context provides it (selected grid cell, row edit modal)
 * and falls back to the field store for contexts that only pass row + field
 * (functional grid cells, cards).
 */
export default {
  data() {
    return {
      dispatching: false,
    }
  },
  computed: {
    resolvedButtonValue() {
      // A broken formula (e.g. referencing a deleted field) must disable
      // the button rather than resolve to a misleading URL.
      const resolved = this.field.error
        ? ''
        : resolveButtonUrl(
            this.$registry,
            this.field,
            this.row,
            this.allFieldsInTable?.length > 0
              ? this.allFieldsInTable
              : this.$store.getters['field/getAll']
          )
      return {
        url: encodeUrlWhitespace(resolved),
        label: this.field.label,
      }
    },
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
        await WorkflowActionService(this.$client).dispatch(
          this.field.id,
          this.row.id
        )
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
  },
}
