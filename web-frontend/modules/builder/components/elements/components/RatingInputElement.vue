<template>
  <div class="rating-element" :key="this.resolvedValue">
    <ABFormGroup
      :label="labelResolved"
      :required="!readOnly && element.required"
      :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    >
      <div>
        <Rating
          v-model="inputValue"
          :max-value="maxValue"
          :custom-color="element.color"
          :rating-style="element.rating_style || 'star'"
          :read-only="readOnly"
          :show-max-value-in-read-only="true"
          @update="onUpdate"
        />
      </div>
    </ABFormGroup>
  </div>
</template>

<script>
import Rating from '@baserow/modules/database/components/Rating'
import formElement from '@baserow/modules/builder/mixins/formElement'
import {
  ensurePositiveInteger,
  ensureString,
} from '@baserow/modules/core/utils/validator'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

export default {
  name: 'RatingInputElement',
  components: {
    Rating,
  },
  mixins: [formElement],
  props: {
    element: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    editing: {
      type: Boolean,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  computed: {
    resolvedValue() {
      try {
        return ensurePositiveInteger(this.resolveFormula(this.element.value))
      } catch {
        return 0
      }
    },
    maxValue() {
      return (
        ensurePositiveInteger(this.element.max_value, { allowNull: true }) || 5
      )
    },
    labelResolved() {
      return ensureString(this.resolveFormula(this.element.label))
    },
    rules() {
      return {
        formElementData: {
          value: this.element.required ? { required } : {},
        },
      }
    },
  },
  validations() {
    return this.rules
  },
  watch: {
    resolvedValue: {
      handler(newValue) {
        this.inputValue = newValue
      },
      immediate: true,
    },
  },
  methods: {
    onUpdate(value) {
      this.inputValue = value
    },
  },
}
</script>
