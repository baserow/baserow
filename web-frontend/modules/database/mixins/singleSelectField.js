import createSelectOption from '@baserow/modules/database/mixins/createSelectOption'
import selectDropdown from '@baserow/modules/database/mixins/selectDropdown'

export default {
  mixins: [createSelectOption, selectDropdown],
  emits: ['update'],
  computed: {
    valueId() {
      return this.value && this.value !== null ? this.value.id : null
    },
  },
  methods: {
    /**
     * Checks if the new value has changed and if so it will be updated.
     */
    updateValue(newId, oldValue) {
      const newValue =
        this.field.select_options.find((option) => option.id === newId) || null
      const oldId = oldValue !== null ? oldValue.id : null

      if (newId !== oldId) {
        this.$emit('update', newValue, oldValue)
      }
    },
  },
}
