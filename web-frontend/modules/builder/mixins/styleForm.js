import _ from 'lodash'
import form from '@baserow/modules/core/mixins/form'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

const borderNames = ['top', 'bottom', 'left', 'right']

const borderStyleNames = borderNames.map((pos) => `style_border_${pos}`)

export default {
  inject: ['builder'],
  props: {
    element: {
      type: Object,
      required: true,
    },
    parentElement: {
      type: Object,
      required: false,
      default: null,
    },
  },
  mixins: [form],
  data() {
    const allowedValues = this.getAllowedValues()
    return {
      allowedValues,
      values: this.getValuesFromElement(allowedValues),
      boxStyles: Object.fromEntries(
        borderNames.map((pos) => [pos, this.getBoxStyleValue(pos)])
      ),
      radiusStyles: {
        background_radius: this.defaultValues.style_background_radius,
        border_radius: this.defaultValues.style_border_radius,
      },
    }
  },
  computed: {
    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
    colorVariables() {
      return ThemeConfigBlockType.getAllColorVariables(
        this.themeConfigBlocks,
        this.builder.theme
      )
    },
    allowedStyles() {
      return this.getAllowedStyles()
    },
    borders() {
      return [
        { name: 'top', label: this.$t('defaultStyleForm.boxTop') },
        { name: 'bottom', label: this.$t('defaultStyleForm.boxBottom') },
        { name: 'left', label: this.$t('defaultStyleForm.boxLeft') },
        { name: 'right', label: this.$t('defaultStyleForm.boxRight') },
      ]
    },
  },
  watch: {
    boxStyles: {
      deep: true,
      handler(newValue) {
        Object.entries(newValue).forEach(([prop, value]) => {
          this.setBoxStyleValue(prop, value)
        })
      },
    },
    radiusStyles: {
      deep: true,
      handler(newValue) {
        Object.entries(newValue).forEach(([prop, value]) => {
          this.setRadiusStyleValue(prop, value)
        })
      },
    },
  },
  methods: {
    isStyleAllowed(style) {
      return this.allowedStyles.includes(style)
    },
    getBoxStyleValue(pos) {
      return {
        margin: this.defaultValues[`style_margin_${pos}`],
        padding: this.defaultValues[`style_padding_${pos}`],
        border_color: this.defaultValues[`style_border_${pos}_color`],
        border_size: this.defaultValues[`style_border_${pos}_size`],
      }
    },
    setBoxStyleValue(pos, newValue) {
      if (newValue.padding !== undefined) {
        this.values[`style_margin_${pos}`] = newValue.margin
        this.values[`style_padding_${pos}`] = newValue.padding
        this.values[`style_border_${pos}_color`] = newValue.border_color
        this.values[`style_border_${pos}_size`] = newValue.border_size
      }
    },
    setRadiusStyleValue(key, newValue) {
      this.values[`style_${key}`] = newValue
    },
    getAllowedStyles() {
      const elementType = this.$registry.get('element', this.element.type)
      const parentElementType = this.parentElement
        ? this.$registry.get('element', this.parentElement?.type)
        : null

      let styles = elementType.styles

      if (parentElementType) {
        styles = _.difference(elementType.styles, [
          ...parentElementType.childStylesForbidden,
        ])
      } else {
        // If the element is a root element, style_width_child is not allowed.
        styles = _.difference(elementType.styles, ['style_width_child'])
      }

      return styles
    },
    getAllowedValues() {
      // Rewrite border style names
      return this.getAllowedStyles()
        .map((style) => {
          if (borderStyleNames.includes(style)) {
            return [`${style}_color`, `${style}_size`]
          }
          return style
        })
        .flat()
    },
    getValuesFromElement(allowedValues) {
      return allowedValues.reduce((obj, value) => {
        obj[value] =
          this.element[value] === undefined ? null : this.element[value]
        return obj
      }, {})
    },
  },
}
