import element from '@baserow/modules/builder/mixins/element'

// Custom controls declare ownership while clicks still reach document handlers.
const interactiveSelector =
  'a, button, input, select, textarea, label, summary, [role="button"], [role="link"], [tabindex], [contenteditable="true"], [data-builder-interactive]'

export default {
  mixins: [element],
  data() {
    return {
      // Whether the clickable element contains links, inputs or other controls.
      hasInteractiveContent: false,
    }
  },
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
    /**
     * Whether the clickable element can render other controls inside it. Elements
     * whose click target only holds text or an image can skip watching their
     * content.
     */
    canContainInteractiveContent() {
      return true
    },
    clickableElementAttributes() {
      if (!this.isClickable) {
        return {}
      }
      // A button's content is presentational, so a button around links or inputs
      // hides them from assistive technology. Such an element stays focusable and
      // keyboard operable without claiming the button role.
      return this.hasInteractiveContent
        ? { tabindex: 0 }
        : { role: 'button', tabindex: 0 }
    },
  },
  watch: {
    isClickable() {
      this.observeInteractiveContent()
    },
  },
  mounted() {
    this.observeInteractiveContent()
  },
  beforeUnmount() {
    this.stopObservingInteractiveContent()
  },
  methods: {
    observeInteractiveContent() {
      this.stopObservingInteractiveContent()
      if (
        !this.isClickable ||
        !this.canContainInteractiveContent ||
        !(this.$el instanceof Element) ||
        typeof MutationObserver === 'undefined'
      ) {
        this.hasInteractiveContent = false
        return
      }

      const update = () => {
        // Only descendants count: the element itself matches `[tabindex]`.
        this.hasInteractiveContent =
          !!this.$el.querySelector(interactiveSelector)
      }
      update()
      this.interactiveContentObserver = new MutationObserver(update)
      this.interactiveContentObserver.observe(this.$el, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: [
          'href',
          'role',
          'tabindex',
          'contenteditable',
          'data-builder-interactive',
        ],
      })
    },
    stopObservingInteractiveContent() {
      this.interactiveContentObserver?.disconnect()
      this.interactiveContentObserver = null
    },
    onElementClick(event) {
      if (
        !this.isClickable ||
        event.defaultPrevented ||
        event.target.closest(interactiveSelector) !== event.currentTarget
      ) {
        return
      }

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
