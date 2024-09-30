<template>
  <div>
    <Button
      v-if="toggleEnabled"
      class="margin-right-1"
      type="secondary"
      @click="$emit('toggle-select-all')"
      >{{ getToggleLabel }}</Button
    >

    <Button
      type="primary"
      :disabled="!inviteEnabled"
      @click="inviteEnabled ? $emit('invite') : null"
      >{{ $t('memberAssignmentModalFooter.invite', { selectedMembersCount }) }}
    </Button>
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
  },
  computed: {
    toggleEnabled() {
      return this.filteredMembersCount !== 0
    },
    inviteEnabled() {
      return this.selectedMembersCount !== 0
    },
    getToggleLabel() {
      return this.allFilteredMembersSelected
        ? this.$t('memberAssignmentModalFooter.deselectAll')
        : this.$t('memberAssignmentModalFooter.selectAll')
    },
  },
}
</script>
