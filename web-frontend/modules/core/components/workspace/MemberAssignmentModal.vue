<template>
  <Modal ref="modal" :full-height="true" :small="true">
    <MemberSelectionList
      ref="memberSelectionList"
      class="padding-top-2"
      :members="members"
      @invite="storeSelectedMembers"
    />
  </Modal>
</template>

<script>
import Modal from '@baserow/modules/core/mixins/modal'
import MemberSelectionList from '@baserow/modules/core/components/workspace/MemberSelectionList'

export default {
  name: 'MemberAssignmentModal',
  components: { MemberSelectionList },
  mixins: [Modal],
  props: {
    members: {
      type: Array,
      required: true,
    },
  },
  emits: ['invite'],
  methods: {
    storeSelectedMembers(membersSelected) {
      this.$emit('invite', membersSelected)
      this.hide()
    },
  },
}
</script>
