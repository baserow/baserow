<template>
  <div class="row">
    <div class="col col-6">
      <Button
        v-if="toggleEnabled"
        type="secondary"
        @click="$emit('toggle-select-all')"
        >{{ getToggleLabel }}</Button
      >
    </div>
    <div class="col col-6 align-right">
      <Button
        type="primary"
        :disabled="!selectEnabled"
        @click="selectEnabled ? $emit('select') : null"
        >{{ actionLabel }}
      </Button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MemberAssignmentModalFooter',
  props: {
    filteredMembersCount: {
      type: Number,
      required: true,
    },
    selectedMembersCount: {
      type: Number,
      required: true,
    },
    allFilteredMembersSelected: {
      type: Boolean,
      required: false,
      default: false,
    },
    buttonLabel: {
      type: String,
      required: false,
      default: null,
    },
    allowEmptySelection: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['select', 'toggle-select-all'],
  computed: {
    toggleEnabled() {
      return this.filteredMembersCount !== 0
    },
    selectEnabled() {
      return this.allowEmptySelection || this.selectedMembersCount !== 0
    },
    actionLabel() {
      return (
        this.buttonLabel ??
        this.$t('memberAssignmentModalFooter.invite', {
          selectedMembersCount: this.selectedMembersCount,
        })
      )
    },
    getToggleLabel() {
      return this.allFilteredMembersSelected
        ? this.$t('memberAssignmentModalFooter.deselectAll')
        : this.$t('memberAssignmentModalFooter.selectAll')
    },
  },
}
</script>
