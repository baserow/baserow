<template>
  <Context class="color-picker-context" @shown="onShown">
    <ColorPicker
      :value="hexColorIncludingAlpha"
      :allow-opacity="allowOpacity"
      @input="setColorFromPicker($event)"
    ></ColorPicker>
    <div class="color-picker-context__color">
      <Dropdown
        v-model="type"
        class="dropdown--floating color-picker-context__color-type"
        :show-search="false"
      >
        <DropdownItem name="Hex" :value="COLOR_NOTATIONS.HEX"></DropdownItem>
        <DropdownItem name="RGB" :value="COLOR_NOTATIONS.RGB"></DropdownItem>
      </Dropdown>
      <div v-if="type === 'hex'" class="color-picker-context__color-hex">
        <FormInput
          ref="hexInput"
          v-model="fakeHexExcludingAlpha"
          small
          @blur="hexChanged"
        />
      </div>
      <div v-if="type === 'rgb'" class="color-picker-context__color-rgb">
        <FormInput
          type="number"
          small
          :min="0"
          :max="255"
          :value="r"
          remove-number-input-controls
          @input="rgbaChanged($event, 'r')"
        />
        <FormInput
          type="number"
          small
          :min="0"
          :max="255"
          :value="g"
          remove-number-input-controls
          @input="rgbaChanged($event, 'g')"
        />
        <FormInput
          type="number"
          small
          :min="0"
          :max="255"
          :value="b"
          remove-number-input-controls
          @input="rgbaChanged($event, 'b')"
        />
      </div>
      <div class="flex-grow-1" />
      <div v-if="allowOpacity" class="color-picker-context__color-opacity">
        <FormInput
          type="number"
          small
          :min="0"
          :max="100"
          :value="a"
          icon-right="iconoir-percentage"
          remove-number-input-controls
          @input="rgbaChanged($event, 'a')"
        />
      </div>
    </div>
    <div
      v-if="Object.keys(variables).length > 0"
      class="color-picker-context__variables"
    >
      <Dropdown
        :value="selectedVariable?.name || ''"
        :placeholder="$t('colorPickerContext.pickColorPlaceholder')"
        @input="setVariable"
      >
        <DropdownItem
          v-for="variable in variables"
          :key="variable.name"
          :name="variable.name"
          :value="variable.name"
        >
          <div
            class="color-picker-context__variable-color"
            :style="{ 'background-color': variable.color }"
          ></div>
          <span class="select__item-name-text" :title="variable.name">
            {{ variable.name }}
          </span>
        </DropdownItem>
      </Dropdown>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import ColorPicker from '@baserow/modules/core/components/ColorPicker.vue'
import {
  isValidHexColor,
  convertHexToRgb,
  convertRgbToHex,
} from '@baserow/modules/core/utils/colors'

export const COLOR_NOTATIONS = {
  HEX: 'hex',
  RGB: 'rgb',
}

export const DEFAULT_COLOR_NOTION = COLOR_NOTATIONS.HEX

export default {
  name: 'ColorPickerContext',
  components: { ColorPicker },
  mixins: [context],
  props: {
    value: {
      type: String,
      required: true,
    },
    variables: {
      type: Array,
      required: false,
      default: () => [],
    },
    allowOpacity: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  data() {
    return {
      hexColorIncludingAlpha: '',
      hexColorExcludingAlpha: '',
      r: 0,
      g: 0,
      b: 0,
      a: 0,
      type: DEFAULT_COLOR_NOTION,
    }
  },
  computed: {
    COLOR_NOTATIONS: () => COLOR_NOTATIONS,
    /**
     * This computed property is used to detect when hexColorExcludingAlpha has
     * changed, then set its value to the new value.
     */
    fakeHexExcludingAlpha: {
      set(newValue) {
        this.hexColorExcludingAlpha = newValue
      },
      get() {
        return this.hexColorExcludingAlpha
      },
    },
    selectedVariable() {
      return this.variables.find(({ value }) => value === this.value)
    },
  },
  watch: {
    value: {
      handler(value, oldValue) {
        // Only update the value if it has actually changed because otherwise the user's
        // input can be overwritten from converting to and from hex values.
        if (value !== oldValue) {
          const variable = this.variables.find(
            (variable) => variable.value === value
          )
          if (variable !== undefined) {
            this.colorUpdated(variable.color)
          } else {
            this.colorUpdated(value)
          }
        }
      },
      immediate: true,
    },
  },
  methods: {
    /**
     * When the user deletes the input field and closes the color picker, upon
     * re-opening the color picker we should display the original persisted
     * value.
     */
    async onShown() {
      if (this.value !== this.fakeHexExcludingAlpha) {
        this.fakeHexExcludingAlpha = this.value
      }
      await this.$nextTick()
      if (this.type === 'hex') this.$refs.hexInput.focus()
    },
    setColorFromPicker(value) {
      if (this.selectedVariable) {
        // If we come from a variable before we reset the alpha channel to 1 otherwise
        // You could think something doesn't work.
        const rgba = convertHexToRgb(value)
        rgba.a = 1
        value = convertRgbToHex(rgba)
      }
      this.colorUpdated(value)
      this.$emit(
        'input',
        this.a === 100
          ? this.hexColorExcludingAlpha
          : this.hexColorIncludingAlpha
      )
    },
    /**
     * Called whenever the original value is updated. It will make sure that all the
     * variables are updated accordingly if the value is a valid hex color.
     */
    colorUpdated(value) {
      if (!isValidHexColor(value)) {
        return
      }

      const rgba = convertHexToRgb(value)

      this.r = rgba.r * 255
      this.g = rgba.g * 255
      this.b = rgba.b * 255

      if (this.allowOpacity) {
        this.a = Math.round(rgba.a * 100)
      } else {
        this.a = 100
      }

      this.hexColorIncludingAlpha = convertRgbToHex(rgba)

      delete rgba.a
      this.hexColorExcludingAlpha = convertRgbToHex(rgba)
    },
    /**
     * Called when one of the RGBA channels must be updated. This is done via one of the
     * text inputs.
     */
    rgbaChanged(event, channel) {
      const value = parseInt(event)
      if (isNaN(value) && value >= 0 && value <= 255) {
        return
      }

      const rgba = convertHexToRgb(this.hexColorIncludingAlpha)
      rgba[channel] = value / (channel === 'a' ? 100 : 255)
      const hex = convertRgbToHex(rgba)

      this.colorUpdated(hex)
      this.$emit('input', hex)
    },
    /**
     * Called when one the raw hex value must be updated.
     */
    hexChanged(event) {
      const value = event.target.value

      // Prefix hash if it isn't present
      let convertedValue = value
      if (!value.startsWith('#')) {
        convertedValue = '#' + convertedValue
      }

      if (!isValidHexColor(convertedValue)) {
        return
      }

      const rgba = convertHexToRgb(this.hexColorIncludingAlpha)
      const newRgba = convertHexToRgb(convertedValue)
      rgba.r = newRgba.r
      rgba.g = newRgba.g
      rgba.b = newRgba.b
      if (rgba.a === 1) {
        delete rgba.a
      }
      const hex = convertRgbToHex(rgba)

      this.colorUpdated(hex)
      this.$emit('input', hex)
    },
    /**
     * Set the color and value based on a variable value.
     */
    setVariable(value) {
      const variable = this.variables.find(
        (variable) => variable.name === value
      )
      if (variable !== undefined) {
        this.colorUpdated(variable.color)
        this.$emit('input', variable.value)
      } else {
        this.$emit('input', this.hexColorIncludingAlpha)
      }
    },
  },
}
</script>
