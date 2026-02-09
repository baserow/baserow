<template>
  <div class="radio-group" :class="{ 'radio-group--vertical': verticalLayout }">
    <template v-for="(option, index) in options" :key="index">
      <Radio
        v-if="type === 'radio'"
        class="radio-group__radio"
        :value="option.value"
        :model-value="currentValue"
        :disabled="option.disabled || option.loading"
        :loading="option.loading"
        :type="type"
        @input="updateValue"
      >
        {{ option.label }}
      </Radio>
      <RadioButton
        v-else
        class="radio-group__radio-button"
        :model-value="currentValue"
        :value="option.value"
        :loading="option.loading"
        :disabled="option.disabled || option.loading"
        :icon="option.icon"
        :title="option.title"
        @input="updateValue"
      >
        <span v-if="option.label">{{ option.label }}</span>
      </RadioButton>
    </template>
  </div>
</template>

<script>
import Radio from '@baserow/modules/core/components/Radio.vue'

export default {
  name: 'RadioGroup',
  components: {
    Radio,
  },
  props: {
    options: {
      type: Array,
      required: true,
    },
    /**
     * The model value of the textarea in Vue 3 style.
     */
    modelValue: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: undefined,
    },
    /**
     * The model value of the textarea in Vue 2 style.
     */
    value: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: undefined,
    },
    verticalLayout: {
      type: Boolean,
      required: false,
      default: false,
    },
    type: {
      type: String,
      required: false,
      default: 'radio',
      validator: (value) => ['radio', 'button'].includes(value),
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    updateValue(value) {
      // emitting the updated value Vue 3 style.
      this.$emit('update:modelValue', value)
      // emitting the updated value Vue 2 style.
      this.$emit('input', value)
    },
  },
}
</script>
