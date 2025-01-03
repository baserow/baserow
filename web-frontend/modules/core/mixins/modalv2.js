/**
 * This mixin is for components that have the Modal component as root element.
 * It will make it easier to call the root modal specific functions.
 */
export default {
  methods: {
    getRootModal() {
      if (
        this.$children.length > 0 &&
        this.$children[0].$options.name === 'ModalV2'
      ) {
        return this.$children[0]
      }
    },
    toggle(...args) {
      this.getRootModal().toggle(...args)
    },
    show(...args) {
      this.getRootModal().show(...args)
    },
    hide(...args) {
      this.getRootModal().hide(...args)
    },
  },
}
