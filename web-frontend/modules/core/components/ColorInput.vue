<template>
  <div :class="{ 'color-input--small': small }">
    <ColorPickerContext
      ref="colorPicker"
      :value="currentValue"
      :variables="localColorVariables"
      :allow-opacity="allowOpacity"
      @input="onValueChange($event)"
    />
    <div
      :id="forInput"
      ref="opener"
      class="color-input__input"
      tabindex="0"
      @click="$refs.colorPicker.toggle($refs.opener)"
    >
      <span
        class="color-input__preview"
        :style="{
          '--selected-color': actualValue,
        }"
      />
      <span class="color-input__text">{{ displayValue }}</span>
    </div>
  </div>
</template>

<script>
import ColorPickerContext from '@baserow/modules/core/components/ColorPickerContext'
import { resolveColor } from '@baserow/modules/core/utils/colors'

export default {
  name: 'ColorInput',
  components: { ColorPickerContext },
  inject: {
    forInput: { from: 'forInput', default: null },
  },
  props: {
    value: {
      type: String,
      required: false,
      default: undefined,
    },
    modelValue: {
      type: String,
      default: undefined,
    },
    colorVariables: {
      type: Array,
      required: false,
      default: () => [],
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    defaultValue: {
      type: String,
      required: false,
      default: null,
    },
    allowOpacity: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    currentValue() {
      return this.modelValue !== undefined
        ? this.modelValue
        : this.value || 'primary'
    },
    variablesMap() {
      return Object.fromEntries(
        this.localColorVariables.map((v) => [v.value, v])
      )
    },
    localColorVariables() {
      if (this.defaultValue) {
        return [
          {
            value: this.defaultValue,
            color: resolveColor(this.defaultValue, this.colorVariables),
            name: this.$t('colorInput.default'),
          },
          ...this.colorVariables,
        ]
      } else {
        return this.colorVariables
      }
    },
    displayValue() {
      const found = this.localColorVariables.find(
        ({ value }) => value === this.currentValue
      )
      if (found) {
        return found.name
      } else {
        return this.currentValue.toUpperCase()
      }
    },
    actualValue() {
      return resolveColor(this.currentValue, this.variablesMap)
    },
  },
  methods: {
    resolveColor,
    onValueChange(event) {
      this.$emit('input', event)
      this.$emit('update:modelValue', event)
    },
  },
}
</script>
