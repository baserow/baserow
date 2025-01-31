<template>
  <Dropdown
    :value="fontWeightValue"
    fixed-items
    @input="$emit('input', $event)"
  >
    <DropdownItem
      v-for="fontWeight in fontWeights"
      :key="fontWeight.type"
      :value="fontWeight.type"
      :name="fontWeight.name"
    />
  </Dropdown>
</template>

<script>
import { FONT_WEIGHTS } from '@baserow/modules/builder/fontWeights'

export default {
  name: 'FontWeightSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: 'Regular',
    },
    font: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    supportedWeights() {
      return this.font ? this.fontFamilyType.weights : ['regular']
    },
    fontFamilyType() {
      return this.$registry.get('fontFamily', this.font)
    },
    fontWeights() {
      return Object.entries(FONT_WEIGHTS)
        .map(([fontType, weight]) => {
          return {
            type: fontType,
            name: this.getFontLabel(fontType),
            weight,
          }
        })
        .filter((fontWeight) => this.supportedWeights.includes(fontWeight.type))
        .sort((a, b) => a.weight - b.weight)
    },
    fontWeightValue: {
      get() {
        return this.value
      },
      set(newValue) {
        this.$emit('input', newValue)
      },
    },
  },

  watch: {
    /**
     * Check if the updated font supports the currently selected weight. If not,
     * set the font weight to 'regular', which should be supported by all fonts.
     */
    font() {
      if (!this.supportedWeights.includes(this.value)) {
        this.fontWeightValue = this.fontFamilyType.defaultWeight
      }
    },
  },

  methods: {
    getFontLabel(fontType) {
      // Convert kebab cased font type, e.g. 'extra-light' to
      // its camel case equivalent, e.g. 'extraLight'
      const fontTypeKebab = fontType.replace(/-([a-z])/g, (_, char) =>
        char.toUpperCase()
      )
      return this.$i18n.t(`fontWeightType.${fontTypeKebab}`)
    },
  },
}
</script>
