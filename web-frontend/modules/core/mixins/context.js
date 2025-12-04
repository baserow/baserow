/**
 * This mixin is for components that have the Context component as root element.
 * It will make it easier to call the root context specific functions.
 */
export default {
  methods: {
    getRootContext() {
      // Search in the refs
      if (this.$refs.context) {
        return this.$refs.context
      }

      throw new Error('Missing context ref in this component')
    },
    toggle(...args) {
      const context = this.getRootContext()
      context && context.toggle(...args)
    },
    toggleNextToMouse(...args) {
      const context = this.getRootContext()
      context && context.toggleNextToMouse(...args)
    },
    show(...args) {
      const context = this.getRootContext()
      context && context.show(...args)
    },
    showNextToMouse(...args) {
      const context = this.getRootContext()
      context && context.showNextToMouse(...args)
    },
    hide(...args) {
      const context = this.getRootContext()
      context && context.hide(...args)
    },
  },
}
