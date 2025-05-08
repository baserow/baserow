import { useVuelidate } from '@vuelidate/core'
/**
 * This mixin can be used with a row edit field if the field only needs an input. For
 * example for the text and number fields. It depends on the rowEditField mixin.
 */
export default {
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      /**
       * Indicates whether the user is editing the value.
       */
      editing: false,
      /**
       * A temporary copy of the value when editing.
       */
      copy: null,
    }
  },
  watch: {
    value(value) {
      if (!this.editing) {
        this.copy = this.prepareCopy(value)
      }
    },
  },
  mounted() {
    this.copy = this.prepareCopy(this.value)
  },
  methods: {
    /**
     * Event that is called when the user starts editing the value. In this case we
     * will only enable the editing state.
     */
    select() {
      if (this.readOnly) {
        return
      }

      this.editing = true
    },
    prepareCopy(value) {
      return value
    },
    prepareValue(copy) {
      return copy
    },
    /**
     * Event that is called when the user finishes editing. If the value is not
     * valid we aren't going to do anything because it can't be changed anyway and
     * we want to give the user a change to fix the value.
     */
    unselect() {
      this.touch()

      if (!this.isValid() || !this.editing) {
        return
      }

      this.editing = false
      this.save()
    },
    /**
     * Saves the value if it has changed. Should only be called by the unselect
     * method and not directly.
     */
    save() {
      if (this.readOnly) {
        return
      }

      const newValue = this.beforeSave(this.copy)

      // If the value hasn't changed we don't want to do anything.
      if (newValue === this.value) {
        this.copy = this.value
      } else {
        this.$emit('update', newValue, this.value)
        this.afterSave()
      }
    },
    /**
     * This method is called before saving the value. Optionally the value can be
     * changed or formatted here if necessary.
     */
    beforeSave(value) {
      return value
    },
    /**
     * Method that is called after saving the value. This can be overridden in the
     * component.
     */
    afterSave() {},
    /**
     * Show the error for the copy value if the user is editing. If we don't do this,
     * then the error message is not showed in real time.
     */
    getError() {
      return this.getValidationError(
        this.editing ? this.prepareValue(this.copy) : this.value
      )
    },
  },
  validations() {
    return {
      copy: {},
    }
  },
}
