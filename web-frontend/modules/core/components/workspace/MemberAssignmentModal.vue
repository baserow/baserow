<template>
  <ModalV2 full-height size="small" :header="false" @show="onShow">
    <template #content>
      <MemberSelectionList
        ref="memberSelectionList"
        class="padding-top-2"
        :members="members"
        :members-selected.sync="membersSelected"
        :members-filtered.sync="membersFiltered"
      />
    </template>
    <template #footer-content>
      <MemberAssignmentModalFooter
        :members="members"
        :all-filtered-members-selected="allFilteredMembersSelected"
        :selected-members-count="membersSelected.length"
        :filtered-members-count="membersFiltered.length"
        @toggle-select-all="toggleSelectAll"
        @invite="storeSelectedMembers"
      />
    </template>
  </ModalV2>
</template>

<script>
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import MemberSelectionList from '@baserow/modules/core/components/workspace/MemberSelectionList'
import MemberAssignmentModalFooter from '@baserow/modules/core/components/workspace/MemberAssignmentModalFooter'

export default {
  name: 'MemberAssignmentModal',
  components: { MemberSelectionList, MemberAssignmentModalFooter },
  mixins: [modalv2],
  props: {
    members: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      membersSelected: [],
      membersFiltered: this.members,
    }
  },
  computed: {
    allFilteredMembersSelected() {
      // Are all members in `membersFiltered` selected?
      return this.membersFiltered.every((member) =>
        this.membersSelected.includes(member)
      )
    },
  },
  methods: {
    storeSelectedMembers() {
      this.$emit('invite', this.membersSelected)
      this.membersSelected = []
      this.hide()
    },
    toggleSelectAll() {
      // If all filtered members are selected...
      if (this.allFilteredMembersSelected) {
        // Exclude those filtered members from the selections.
        this.membersSelected = this.membersSelected.filter(
          (member) => !this.membersFiltered.includes(member)
        )
      } else {
        // We have new filtered members to add to the selections.
        const membersToAdd = this.membersFiltered.filter(
          (member) => !this.membersSelected.includes(member)
        )
        this.membersSelected = this.membersSelected.concat(membersToAdd)
      }
    },
    onShow() {
      this.membersFiltered = this.members
    },
  },
}
</script>
