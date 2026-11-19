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
          <CollaboratorAvatar
            class="select-collaborators__initials"
            :collaborator="{ ...user, id: user.user_id }"
          />
          <div class="select-collaborators__dropdown-option">
            {{ user.name }}
          </div>
        </li>
      </ul>
    </template>
  </div>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
export default {
  components: { CollaboratorAvatar },
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
    }
  },
  computed: {
    filteredUsers() {
      return this.users.filter(
        (user) =>
          !user.to_be_deleted &&
          (!this.query ||
            user.name.toLowerCase().includes(this.query.toLowerCase()) ||
            `${user.user_id}` === this.query)
      )
    },
  },
  watch: {
    query() {
      this.selectedIndex = 0
    },
    users() {
      this.selectedIndex = 0
    },
  },

  methods: {
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

      if (item) {
        this.command({ id: item.user_id, label: item.name })
      }
    },
  },
}
</script>
