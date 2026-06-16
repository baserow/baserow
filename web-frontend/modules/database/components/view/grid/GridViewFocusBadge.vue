<template>
  <div v-if="entries.length > 0" class="grid-view__focus-badge">
    <div
      class="grid-view__focus-badge-item"
      :style="{ backgroundColor: anchorColor }"
    >
      <span v-if="isEditing" class="grid-view__focus-badge-typing">
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
      </span>
      <template v-else>
        {{ anchorInitials }}
        <span v-if="overflowCount > 0" class="grid-view__focus-badge-count">
          +{{ overflowCount }}
        </span>
      </template>
    </div>
  </div>
</template>

<script>
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

export default {
  name: 'GridViewFocusBadge',
  props: {
    entries: {
      type: Array,
      default: () => [],
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
    anchorInitials() {
      return this.anchorUser ? nameAbbreviation(this.anchorUser.name) : '?'
    },
    anchorColor() {
      return this.anchorEntry ? this.anchorEntry.color : undefined
    },
    overflowCount() {
      return Math.max(0, this.entries.length - 1)
    },
    isEditing() {
      return this.entries.some((e) => e.editing)
    },
  },
}
</script>
