/**
 * A mixin that can be used in combination with the view filter input components. If
 * contains the expected props and it has a computed property that finds the field
 * object related to filter field id.
 */
export default {
  props: {
    view: {
      type: Object,
      required: false,
      default: undefined,
    },
    isPublicView: {
      type: Boolean,
      required: false,
      default: false,
    },
    filter: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
  },
  computed: {
    field() {
      return this.fields.find((f) => f.id === this.filter.field)
    },
    primary() {
      return this.fields.find((f) => f.primary)
    },
    filterType() {
      return this.$registry.get('viewFilter', this.filter.type)
    },
  },
}
