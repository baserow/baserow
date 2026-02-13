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
        :disabled="!inviteEnabled"
        @click="inviteEnabled ? $emit('invite') : null"
        >{{
          $t('memberAssignmentModalFooter.invite', { selectedMembersCount })
        }}
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
  },
  emits: ['invite', 'toggle-select-all'],
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
