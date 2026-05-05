<template>
  <Modal ref="modal" :full-height="true" :small="true">
    <MemberSelectionList
      ref="memberSelectionList"
      class="padding-top-2"
      :members="members"
      :selected-members="selectedMembers"
      :allow-empty-selection="allowEmptySelection"
      :button-label="buttonLabel"
      @select="storeSelectedMembers"
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
    selectedMembers: {
      type: Array,
      required: false,
      default: () => [],
    },
    allowEmptySelection: {
      type: Boolean,
      required: false,
      default: false,
    },
    buttonLabel: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['select'],
  methods: {
    storeSelectedMembers(membersSelected) {
      this.$emit('select', membersSelected)
      this.hide()
    },
  },
}
</script>
