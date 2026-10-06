<template>
  <div>
    <template v-if="items.length">
      <ul class="rich-text-editor__mention-list">
        <template
          v-for="(item, index) in items"
          :key="`${item.kind}-${item.id}`"
        >
          <li
            v-if="showSections && index === firstIndexOfKind(item.kind)"
            class="rich-text-editor__mention-list-section"
          >
            {{
              item.kind === 'application'
                ? $t('richTextEditor.mentionAgents')
                : $t('richTextEditor.mentionMembers')
            }}
          </li>
          <li
            ref="item"
            class="rich-text-editor__mention-list-item"
            :class="{ 'is-selected': index === selectedIndex }"
            @click.stop.prevent="selectItem(index)"
          >
            <div
              v-if="item.kind === 'application'"
              class="rich-text-editor__mention-list-agent-icon"
            >
              <i class="baserow-icon-agent"></i>
            </div>
            <div v-else class="select-collaborators__initials">
              {{ initials(item) }}
            </div>
            <div class="select-collaborators__dropdown-option">
              {{ item.name }}
            </div>
          </li>
        </template>
      </ul>
    </template>
  </div>
</template>

<script>
export default {
  props: {
    users: {
      type: Array,
      required: true,
    },
    /**
     * Agents that asked to be mentioned on this table, as
     * `{ id, name }`; empty where comments cannot address an agent.
     */
    agents: {
      type: Array,
      required: false,
      default: () => [],
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
      items: [],
    }
  },

  computed: {
    showSections() {
      return this.items.some((item) => item.kind === 'application')
    },
  },

  watch: {
    workspace() {
      this.selectedIndex = 0
    },
    query: {
      handler(query, oldQuery) {
        const matches = (name, id) =>
          !query ||
          name.toLowerCase().includes(query.toLowerCase()) ||
          `${id}` === query
        this.items = [
          ...this.users
            .filter((user) => matches(user.name, user.user_id))
            .map((user) => ({
              kind: 'user',
              id: user.user_id,
              name: user.name,
            })),
          ...this.agents
            .filter((agent) => matches(agent.name, agent.id))
            .map((agent) => ({
              kind: agent.type || 'application',
              id: agent.id,
              name: agent.name,
            })),
        ]
        if (query !== oldQuery) {
          this.selectedIndex = 0
        }
      },
      immediate: true,
    },
  },

  methods: {
    initials(item) {
      return item.name.slice(0, 1).toUpperCase()
    },
    firstIndexOfKind(kind) {
      return this.items.findIndex((item) => item.kind === kind)
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
        const listItem = this.$refs.item?.[this.selectedIndex]
        listItem?.scrollIntoView({ behavior: 'auto', block: 'nearest' })
      })
    },
    upHandler() {
      if (this.selectedIndex === 0) return

      this.selectedIndex = this.selectedIndex - 1

      this.scrollSelectedIntoView()
    },

    downHandler() {
      if (this.selectedIndex === this.items.length - 1) return

      this.selectedIndex = this.selectedIndex + 1
      this.scrollSelectedIntoView()
    },

    enterHandler() {
      this.selectItem(this.selectedIndex)
    },

    selectItem(index) {
      const item = this.items[index]

      if (item) {
        this.command({ id: item.id, label: item.name, kind: item.kind })
      }
    },
  },
}
</script>
