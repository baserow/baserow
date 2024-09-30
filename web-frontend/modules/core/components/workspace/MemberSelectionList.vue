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
      @selected="memberSelected($event)"
    >
      <template #left-side="{ item }">
        <Avatar
          class="margin-left-1"
          rounded
          size="medium"
          :initials="item.name | nameAbbreviation"
        ></Avatar>

        <span class="margin-left-1">
          {{ item.name }}
        </span>
      </template>
    </List>
  </div>
</template>

<script>
export default {
  name: 'MemberSelectionList',
  props: {
    members: {
      type: Array,
      required: true,
      default: () => [],
    },
    membersSelected: {
      type: Array,
      required: true,
      default: () => [],
    },
  },
  data() {
    return {
      membersFiltered: this.members,
      activeSearchTerm: null,
    }
  },
  computed: {
    searchAbleAttributes() {
      return ['name', 'email']
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
  beforeDestroy() {
    this.$priorityBus.$off('start-search', this.searchStarted)
  },
  methods: {
    searchStarted({ event }) {
      event.preventDefault()
      this.$refs.searchInput.focus()
    },
    search(value) {
      if (value === null || value === '' || this.members.length === 0)
        this.membersFiltered = this.members

      this.membersFiltered = this.members.filter((member) =>
        this.searchAbleAttributes.some((attribute) =>
          member[attribute].toLowerCase().includes(value.toLowerCase())
        )
      )

      this.$emit('update:membersFiltered', this.membersFiltered)
    },
    memberSelected({ value, item }) {
      if (value) this.membersSelected.push(item)
      else {
        const index = this.membersSelected.findIndex(
          (member) => member.id === item.id
        )
        this.membersSelected.splice(index, 1)
      }

      this.$emit('update:membersSelected', this.membersSelected)
    },
  },
}
</script>
