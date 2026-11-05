<template>
  <div>
    <template v-if="filteredUsers.length">
      <ul class="rich-text-editor__mention-list">
        <li
          v-for="(user, index) in filteredUsers"
          :key="index"
          ref="user"
          class="rich-text-editor__mention-list-item"
          :class="{ 'is-selected': index === selectedIndex }"
          @click.stop.prevent="selectItem(index)"
        >
          <div class="select-collaborators__initials">
            {{ userInitials(user) }}
          </div>
          <div class="select-collaborators__dropdown-option">
            {{ user.name }}
          </div>
        </li>
      </ul>
    </template>
  </div>
</template>

<script>
import { getCollaboratorSubjectType } from '@baserow/modules/core/utils/collaborator'

export default {
  props: {
    users: {
      type: Array,
      required: true,
    },

    command: {
      type: Function,
      required: true,
    },
    query: {
      type: String,
      required: true,
    },
  },

  data() {
    return {
      selectedIndex: 0,
      filteredUsers: [],
    }
  },

  watch: {
    workspace() {
      this.selectedIndex = 0
    },
    query: {
      handler(query, oldQuery) {
        this.filteredUsers = this.users.filter(
          (user) =>
            getCollaboratorSubjectType(user, this.$registry).isUser() &&
            Number.isInteger(user.user_id) &&
            (!query ||
              user.name.toLowerCase().includes(query.toLowerCase()) ||
              `${user.user_id}` === query)
        )
        if (query !== oldQuery) {
          this.selectedIndex = 0
        }
      },
      immediate: true,
    },
  },

  methods: {
    userInitials(user) {
      return user.name.slice(0, 1).toUpperCase()
    },
    onKeyDown({ event }) {
      if (event.key === 'ArrowUp') {
        this.upHandler()
        return true
      }

      if (event.key === 'ArrowDown') {
        this.downHandler()
        return true
      }

      if (event.key === 'Enter' || event.key === 'Tab') {
        this.enterHandler()
        event.preventDefault()
        event.stopPropagation()
        return true
      }

      return false
    },
    scrollSelectedIntoView() {
      this.$nextTick(() => {
        const listItem = this.$refs.user[this.selectedIndex]
        listItem.scrollIntoView({ behavior: 'auto', block: 'nearest' })
      })
    },
    upHandler() {
      if (this.selectedIndex === 0) return

      this.selectedIndex = this.selectedIndex - 1

      this.scrollSelectedIntoView()
    },

    downHandler() {
      if (this.selectedIndex === this.filteredUsers.length - 1) return

      this.selectedIndex = this.selectedIndex + 1
      this.scrollSelectedIntoView()
    },

    enterHandler() {
      this.selectItem(this.selectedIndex)
    },

    selectItem(index) {
      const item = this.filteredUsers[index]

      if (
        item &&
        Number.isInteger(item.user_id) &&
        getCollaboratorSubjectType(item, this.$registry).isUser()
      ) {
        this.command({ id: item.user_id, label: item.name })
      }
    },
  },
}
</script>
