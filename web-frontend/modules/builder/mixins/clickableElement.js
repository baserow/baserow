import element from '@baserow/modules/builder/mixins/element'

const interactiveSelector =
  'a, button, input, select, textarea, label, summary, [role="button"], [role="link"], [tabindex], [contenteditable="true"]'

export default {
  mixins: [element],
  computed: {
    isClickable() {
      // Repeated editor previews override `mode`, but retain the editing context.
      if (this.isEditMode || this.applicationContext.mode === 'editing') {
        return false
      }

      return this.$store.getters[
        'builderWorkflowAction/getElementWorkflowActions'
      ](this.elementPage, this.element.id).some(
        ({ event }) => event === 'click'
      )
    },
    clickableElementAttributes() {
      return this.isClickable ? { role: 'button', tabindex: 0 } : {}
    },
  },
  methods: {
    onElementClick(event) {
      if (
        !this.isClickable ||
        event.defaultPrevented ||
        event.target.closest(interactiveSelector) !== event.currentTarget
      ) {
        return
      }

      event.stopPropagation()
      return this.fireEvent(
        this.elementType.getEventByName(this.element, 'click')
      )
    },
    onElementKeydown(event) {
      if (
        !this.isClickable ||
        event.target !== event.currentTarget ||
        !['Enter', ' '].includes(event.key)
      ) {
        return
      }

      event.preventDefault()
      if (event.key === 'Enter') {
        event.currentTarget.click()
      }
    },
    onElementKeyup(event) {
      if (
        this.isClickable &&
        event.target === event.currentTarget &&
        event.key === ' '
      ) {
        event.preventDefault()
        event.currentTarget.click()
      }
    },
  },
}
