/**
 * A mixin that can be used by child form components to register themselves with their parent form.
 */
export default {
  props: {
    parentForm: {
      type: Object,
      required: false,
      default: null,
    },
  },
  mounted() {
    if (this.parentForm && this.parentForm.registerChildForm) {
      this.parentForm.registerChildForm(this)
    }
  },
  beforeDestroy() {
    if (this.parentForm && this.parentForm.unregisterChildForm) {
      this.parentForm.unregisterChildForm(this)
    }
  },
}
