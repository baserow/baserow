import _ from 'lodash'
import formElement from '@baserow/modules/builder/mixins/formElement'

export default {
  mixins: [formElement],
  methods: {
    async onSelectionChange(value) {
      if (this.workflowActionsInProgress) return

      const changed = !_.isEqual(this.inputValue, value)
      this.inputValue = value
      this.handleFormElementChange()

      if (
        !changed ||
        this.isEditMode ||
        this.applicationContext.mode === 'editing'
      ) {
        return
      }

      // Let formElement's watcher store the value before action formulas read it.
      await this.$nextTick()
      return this.fireEvent(
        this.elementType.getEventByName(this.element, 'change')
      )
    },
  },
}
