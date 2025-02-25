<template>
  <FieldCollaboratorDropdown
    :collaborators="workspaceCollaborators"
    :disabled="disabled"
    :value="copy"
    :show-empty-value="false"
    :fixed-items="true"
    :initial-display-name="initialDisplayName"
    class="dropdown--floating filters__value-dropdown"
    @input="input"
  ></FieldCollaboratorDropdown>
</template>

<script>
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'
import viewFilter from '@baserow/modules/database/mixins/viewFilter'
import availableCollaborators from '@baserow/modules/database/mixins/availableCollaborators'

export default {
  name: 'ViewFilterTypeSelectOptions',
  components: { FieldCollaboratorDropdown },
  mixins: [viewFilter, availableCollaborators],
  computed: {
    copy() {
      const value = this.filter.value
      return value === '' ? null : parseInt(value) || null
    },
    initialDisplayName() {
      const selected = this.workspaceCollaborators.find(
        (c) => c.id === this.copy
      )
      return selected?.name
    },
  },
  methods: {
    input(value) {
      value = value === null ? '' : value.toString()
      this.$emit('input', value)
    },
  },
}
</script>
