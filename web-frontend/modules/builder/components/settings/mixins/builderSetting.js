/**
 * A mixin for the builder setting components which have forms. This mixin makes
 * it easier to make them immediately display their "create" form from the parent
 * builder settings modal. When `force-display-form` is set, the end-user doesn't
 * have to click a "New" button.
 */
export default {
  props: {
    builder: {
      type: Object,
      required: true,
    },
    forceDisplayForm: {
      type: Boolean,
      required: false,
      default: false,
    },
    hideAfterCreate: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      showForm: false,
    }
  },
  mounted() {
    if (this.forceDisplayForm) {
      this.showForm = true
    }
  },
  methods: {
    hideModalIfRequired(createdRecordId) {
      if (this.hideAfterCreate) {
        this.$emit('hide-modal', createdRecordId)
      }
    },
  },
}
