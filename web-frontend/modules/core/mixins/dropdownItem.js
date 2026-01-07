import { escapeRegExp } from '@baserow/modules/core/utils/string'

export default {
  emits: ['click'],

  inject: ['multiple', 'dropdownProvider'],
  props: {
    value: {
      validator: () => true,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    alias: {
      type: String,
      required: false,
    },
    icon: {
      type: String,
      required: false,
      default: null,
    },
    image: {
      type: String,
      required: false,
      default: null,
    },
    iconTooltip: {
      type: String,
      required: false,
      default: null,
    },
    description: {
      type: String,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    visible: {
      type: Boolean,
      required: false,
      default: true,
    },
    indented: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      // This field is being used by `getDropdownItemComponents` in ``dropdown.js to
      // figure out if the child component is a dropdown item or not
      isDropdownItem: true,
      query: '',
    }
  },
  computed: {
    // Retrieve the first parent of this component that has 'isDropdown'
    // property set.
    parent() {
      let parent = this.$parent
      while (parent) {
        if (parent.isDropdown) {
          return parent
        }
        parent = parent.$parent
      }
      return parent
    },
  },
  mounted() {
    // Register with parent dropdown
    if (this.dropdownProvider && this.dropdownProvider.registerDropdownItem) {
      this.dropdownProvider.registerDropdownItem(this)
    }
  },
  beforeUnmount() {
    // Unregister from parent dropdown
    if (this.dropdownProvider && this.dropdownProvider.unregisterDropdownItem) {
      this.dropdownProvider.unregisterDropdownItem(this)
    }
  },
  methods: {
    select(value, disabled) {
      if (!disabled) {
        this.parent.select(value)
      }
      this.$emit('click', value)
    },
    hover(value, disabled) {
      if (!disabled && this.parent.focusedDropdownItem !== value) {
        this.parent.focusedDropdownItem = value
      }
    },
    search(query) {
      this.query = query
      return this.isVisible(query)
    },
    isVisible(query) {
      if (!query) return true
      if (query.trim().length === 0) return false
      const regex = new RegExp('(' + escapeRegExp(query) + ')', 'i')
      return Boolean(this.name.match(regex) || this.alias?.match(regex))
    },
    isActive(value) {
      if (this.multiple.value) {
        const parentValue = this.parent.currentValue ?? []
        return parentValue.includes(value)
      } else {
        return this.parent.currentValue === value
      }
    },
    isHovering(value) {
      return this.parent.focusedDropdownItem === value
    },
  },
}
