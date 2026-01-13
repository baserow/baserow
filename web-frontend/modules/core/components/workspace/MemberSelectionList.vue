<template>
  <div class="select-members-list">
    <div>
      <FormInput
        ref="searchInput"
        v-model="activeSearchTerm"
        :placeholder="$t('memberSelectionList.searchPlaceholder')"
      ></FormInput>
      <div class="margin-top-2">
        {{
          $t('memberSelectionList.selectedAmountLabel', {
            count: membersSelected.length,
          })
        }}
      </div>
    </div>
    <List
      class="margin-top-2 select-members-list__items"
      :items="membersFiltered"
      :selected-items="membersSelected"
      :attributes="['email']"
      selectable
      @selected="memberSelected"
    >
      <template #left-side="{ item }">
        <Avatar
          class="margin-left-1"
          rounded
          size="medium"
          :initials="$filters.nameAbbreviation(item.name)"
        ></Avatar>

        <span class="margin-left-1">
          {{ item.name }}
        </span>
      </template>
    </List>
    <MemberAssignmentModalFooter
      :all-filtered-members-selected="allFilteredMembersSelected"
      :selected-members-count="membersSelected.length"
      :filtered-members-count="membersFiltered.length"
      @toggle-select-all="toggleSelectAll"
      @invite="$emit('invite', membersSelected)"
    />
  </div>
</template>

<script>
import MemberAssignmentModalFooter from '@baserow/modules/core/components/workspace/MemberAssignmentModalFooter'
export default {
  name: 'MemberSelectionList',
  components: { MemberAssignmentModalFooter },
  props: {
    members: {
      type: Array,
      required: true,
    },
  },
  emits: ['invite'],
  data() {
    return {
      membersFiltered: this.members,
      membersSelected: [],
      activeSearchTerm: null,
    }
  },
  computed: {
    searchAbleAttributes() {
      return ['name', 'email']
    },
    allFilteredMembersSelected() {
      // Are all members in `membersFiltered` selected?
      return this.membersFiltered.every((member) =>
        this.membersSelected.includes(member)
      )
    },
  },
  watch: {
    activeSearchTerm(newValue) {
      this.search(newValue)
    },
  },
  mounted() {
    this.$priorityBus.$on(
      'start-search',
      this.$priorityBus.level.HIGH,
      this.searchStarted
    )
  },
  beforeUnmount() {
    this.$priorityBus.$off('start-search', this.searchStarted)
  },
  methods: {
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
    searchStarted({ event }) {
      event.preventDefault()
      this.$refs.searchInput.focus()
    },
    search(value) {
      if (value === null || value === '' || this.members.length === 0) {
        this.membersFiltered = this.members
      }

      this.membersFiltered = this.members.filter((member) =>
        this.searchAbleAttributes.some((attribute) =>
          member[attribute].toLowerCase().includes(value.toLowerCase())
        )
      )
    },
    memberSelected({ value, item }) {
      if (value) {
        this.membersSelected.push(item)
      } else {
        const index = this.membersSelected.findIndex(
          (member) => member.id === item.id
        )
        this.membersSelected.splice(index, 1)
      }
    },
  },
}
</script>
