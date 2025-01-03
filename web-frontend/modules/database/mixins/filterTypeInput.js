import viewFilter from '@baserow/modules/database/mixins/viewFilter'

let delayTimeout = null

/**
 * Mixin that introduces a delayedUpdate helper method. This method is specifically
 * helpful in combination with an input field that accepts any form of text. When the
 * user stops typing for 400ms it will do the actual update, but only if the validation
 * passes.
 */
export default {
  mixins: [viewFilter],
  data() {
    return {
      copy: null,
      // This can be used to avoid changing the value if the user is editing it
      // Or can be set i.e. by onFocus event
      focused: false,
    }
  },
  watch: {
    'filter.value'(value, oldValue) {
      if (!this.focused) {
        this.copy = this.prepareCopy(this.filter.value)
        if (oldValue !== value) {
          this.afterValueChanged(value, oldValue)
        }
      }
      clearTimeout(delayTimeout)
    },
  },
  created() {
    this.copy = this.prepareCopy(this.filter.value)
    if (this.copy) {
      this.$v.$touch()
    }
  },
  methods: {
    isInputValid() {
      return !this.$v.copy.$error
    },
    prepareCopy(value) {
      return value
    },
    prepareValue(value) {
      return String(value ?? '').trim()
    },
    afterValueChanged(value, oldValue) {},
    delayedUpdate(value, immediately = false) {
      if (this.disabled) {
        return
      }

      clearTimeout(delayTimeout)
      this.$v.$touch()

      if (!this.isInputValid()) {
        return
      }

      const preparedValue = this.prepareValue(value)
      if (immediately) {
        this.$emit('input', preparedValue)
      } else {
        delayTimeout = setTimeout(() => {
          this.$emit('input', preparedValue)
        }, 400)
      }
    },
  },
  validations: {
    copy: {},
  },
}
