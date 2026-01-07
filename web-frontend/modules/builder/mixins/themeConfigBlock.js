import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'
import form from '@baserow/modules/core/mixins/form'
import { clone } from '@baserow/modules/core/utils/object'
import _ from 'lodash'

export default {
  inject: ['builder'],
  mixins: [form],
  emits: ['values-changed'],
  props: {
    preview: {
      type: Boolean,
      required: false,
      default: true,
    },
    extraArgs: {
      type: Object,
      required: false,
      default: null,
    },
    theme: { type: Object, required: false, default: null },
  },
  data() {
    return { values: {} }
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
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        const updated = { ...this.defaultValues, ...newValues }
        const reference = this.theme ? this.theme : this.defaultValues

        // We remove values that are equals to theme values to react on theme change
        // if there is no value
        const differences = Object.fromEntries(
          Object.entries(updated).filter(
            ([key, value]) => !_.isEqual(value, reference[key])
          )
        )
        this.$emit('values-changed', differences)
      }
    },
    // Overrides form mixin getDefaultValues to merge theme values with existing values
    getDefaultValues() {
      if (this.allowedValues === null) {
        if (this.theme) {
          return { ...clone(this.theme), ...clone(this.defaultValues) }
        } else {
          return clone(this.defaultValues)
        }
      }
      const mergedValues = { ...this.theme, ...this.defaultValues }
      return Object.keys(mergedValues).reduce((result, key) => {
        if (this.allowedValues.includes(key)) {
          let value = mergedValues[key]

          // If the value is an array or object, it could be that it contains
          // references and we actually need a copy of the value here so that we don't
          // directly change existing variables when editing form values.
          if (
            Array.isArray(value) ||
            (typeof value === 'object' && value !== null)
          ) {
            value = clone(value)
          }

          result[key] = value
        }
        return result
      }, {})
    },
  },
}
