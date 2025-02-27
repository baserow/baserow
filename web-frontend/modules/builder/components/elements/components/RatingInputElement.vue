<template>
  <div class="rating-element">
    <ABFormGroup
      :label="labelResolved"
      :required="!readOnly && element.required"
      :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    >
      <div class="rating" :style="{ '--rating-color': element.color }">
        <Rating
          :value="displayValue"
          :max-value="maxValue"
          :color="'custom'"
          :rating-style="element.style || 'star'"
          :read-only="readOnly"
          :show-unselected-in-read-only="true"
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
    displayValue() {
      if (this.readOnly || this.editing) {
        return this.resolvedValue
      }
      return this.formElementData?.value ?? this.resolvedValue
    },
    rules() {
      return {
        formElementData: {
          value: this.element.required ? { required } : {}
        }
      }
    }
  },
  validations() {
    return this.rules
  },
  watch: {
    resolvedValue: {
      handler(newValue) {
        if (!this.readOnly && this.formElementData?.value === undefined) {
          this.setFormData(newValue)
        }
      },
    },
  },
  mounted() {
    this.setFormData(this.resolvedValue)
  },
  methods: {
    onUpdate(value) {
      this.handleFormElementChange(value)
    },
  },
}
</script>
