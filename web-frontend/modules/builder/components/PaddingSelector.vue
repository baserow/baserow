<template>
  <div class="padding-selector">
    <FormInput
      :value="value.horizontal"
      :default-value-when-empty="
        defaultValuesWhenEmpty ? defaultValuesWhenEmpty[`horizontal`] : null
      "
      type="number"
      remove-number-input-controls
      :to-value="(value) => (value ? parseInt(value) : null)"
      class="padding-selector__input"
      icon-right="iconoir-horizontal-split"
      @input="$emit('input', { horizontal: $event, vertical: value.vertical })"
      @blur="$emit('blur')"
    />
    <FormInput
      :value="value.vertical"
      :default-value-when-empty="
        defaultValuesWhenEmpty ? defaultValuesWhenEmpty[`vertical`] : null
      "
      type="number"
      remove-number-input-controls
      :to-value="(value) => (value ? parseInt(value) : null)"
      class="padding-selector__input"
      icon-right="iconoir-vertical-split"
      @input="
        $emit('input', { horizontal: value.horizontal, vertical: $event })
      "
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
      required: true,
    },
    defaultValuesWhenEmpty: {
      type: Object,
      required: false,
      default: null,
    },
  },
}
</script>
