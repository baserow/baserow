<template>
  <div :class="{ 'color-input--small': small }">
    <ColorPickerContext
      ref="colorPicker"
      :value="value"
      :variables="localColorVariables"
      :allow-opacity="allowOpacity"
      @input="$emit('input', $event)"
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
      default: 'primary',
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
  computed: {
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
        ({ value }) => value === this.value
      )
      if (found) {
        return found.name
      } else {
        return this.value.toUpperCase()
      }
    },
    actualValue() {
      return resolveColor(this.value, this.variablesMap)
    },
  },
  methods: { resolveColor },
}
</script>
