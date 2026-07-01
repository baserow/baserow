<template>
  <div v-if="entries.length > 0" class="grid-view__focus-badge">
    <div
      class="grid-view__focus-badge-item"
      :style="badgeStyle"
      :title="allNames"
    >
      <span v-if="isEditing" class="grid-view__focus-badge-typing">
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
      </span>
      <template v-else>
        <span class="grid-view__focus-badge-name">
          {{ anchorName }}
        </span>
        <span v-if="overflowCount > 0" class="grid-view__focus-badge-count">
          +{{ overflowCount }}
        </span>
      </template>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GridViewFocusBadge',
  props: {
    entries: {
      type: Array,
      default: () => [],
    },
    maxWidth: {
      type: Number,
      default: 120,
    },
  },
  computed: {
    anchorEntry() {
      return this.entries[0] || null
    },
    anchorUser() {
      if (!this.anchorEntry) return null
      return this.$store.getters['workspace/getUserById'](
        this.anchorEntry.user_id
      )
    },
    anchorName() {
      return this.anchorUser ? this.anchorUser.name : '?'
    },
    anchorColor() {
      return this.anchorEntry ? this.anchorEntry.color : undefined
    },
    allNames() {
      return this.entries
        .map((e) => {
          const user = this.$store.getters['workspace/getUserById'](e.user_id)
          const name = user ? user.name : '?'
          return e.editing ? `${name} (editing)` : name
        })
        .join(', ')
    },
    overflowCount() {
      return Math.max(0, this.entries.length - 1)
    },
    isEditing() {
      return this.entries.some((e) => e.editing)
    },
    badgeStyle() {
      return {
        backgroundColor: this.anchorColor,
        maxWidth: this.maxWidth + 'px',
      }
    },
  },
}
</script>
