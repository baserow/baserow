import viewFilter from '@baserow/modules/database/mixins/viewFilter'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

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
      v$: null,
      values: null,
    }
  },
  watch: {
    'filter.value'(value) {
      const oldValue = this.copy
      this.values.copy = value
      clearTimeout(delayTimeout)
      if (oldValue !== value) {
        this.afterValueChanged(value, oldValue)
      }
    },
  },
  created() {
    const values = reactive({
      copy: this.filter.value,
    })

    const rules = computed(() => ({
      copy: {},
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values

    if (this.values.copy) {
      this.v$.$touch()
    }
  },
  methods: {
    isInputValid() {
      return !this.v$.copy.$error
    },
    afterValueChanged(value, oldValue) {},
    delayedUpdate(value, immediately = false) {
      if (this.disabled) {
        return
      }

      clearTimeout(delayTimeout)
      this.v$.$touch()

      if (!this.isInputValid()) {
        return
      }

      if (immediately) {
        this.$emit('input', value)
      } else {
        delayTimeout = setTimeout(() => {
          this.$emit('input', value)
        }, 400)
      }
    },
  },
}
