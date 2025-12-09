<template>
  <div class="radio-group" :class="{ 'radio-group--vertical': verticalLayout }">
    <template v-for="(option, index) in options" :key="index">
      <Radio
        v-if="type === 'radio'"
        class="radio-group__radio"
        :value="option.value"
        :model-value="modelValue"
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
        :model-value="modelValue"
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
  model: {
    prop: 'modelValue',
    event: 'input',
  },
  props: {
    options: {
      type: Array,
      required: true,
    },
    modelValue: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
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
  methods: {
    updateValue(value) {
      this.$emit('input', value)
    },
  },
}
</script>
