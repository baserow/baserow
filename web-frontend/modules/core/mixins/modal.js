/**
 * This mixin is for components that have the Modal component as root element.
 * It will make it easier to call the root modal specific functions.
 */
export default {
  methods: {
    getRootModal() {
      // Search in the refs
      if (this.$refs.modal) {
        return this.$refs.modal
      }

      return null
    },
    toggle(...args) {
      const modal = this.getRootModal()
      modal && modal.toggle(...args)
    },
    show(...args) {
      const modal = this.getRootModal()
      modal && modal.show(...args)
    },
    hide(...args) {
      const modal = this.getRootModal()
      modal && modal.hide(...args)
    },
  },
}
