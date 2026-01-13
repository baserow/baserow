<template>
  <div class="padding-selector">
    <FormInput
      :value="currentValue.horizontal"
      :default-value-when-empty="
        defaultValuesWhenEmpty ? defaultValuesWhenEmpty[`horizontal`] : null
      "
      type="number"
      remove-number-input-controls
      :to-value="(value) => (value ? parseInt(value) : null)"
      class="padding-selector__input"
      icon-right="iconoir-horizontal-split"
      @input="emit({ horizontal: $event, vertical: currentValue.vertical })"
      @blur="$emit('blur')"
    />
    <FormInput
      :value="currentValue.vertical"
      :default-value-when-empty="
        defaultValuesWhenEmpty ? defaultValuesWhenEmpty[`vertical`] : null
      "
      type="number"
      remove-number-input-controls
      :to-value="(value) => (value ? parseInt(value) : null)"
      class="padding-selector__input"
      icon-right="iconoir-vertical-split"
      @input="emit({ horizontal: currentValue.horizontal, vertical: $event })"
      @blur="$emit('blur')"
    />
  </div>
</template>

<script>
export default {
  name: 'PaddingSelector',
  props: {
    value: {
      type: Object,
      default: undefined,
    },
    modelValue: {
      type: Object,
      default: undefined,
    },
    defaultValuesWhenEmpty: {
      type: Object,
      required: false,
      default: null,
    },
  },
  emits: ['input', 'blur', 'update:modelValue'],
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    emit(newValue) {
      this.$emit('input', newValue)
      this.$emit('update:modelValue', newValue)
    },
  },
}
</script>
