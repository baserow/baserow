<template>
  <div v-if="entries.length > 0" class="grid-view__focus-badge">
    <div class="grid-view__focus-badge-item" :style="badgeStyle">
      <span v-if="isEditing" class="grid-view__focus-badge-typing">
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
        <span class="grid-view__focus-badge-dot"></span>
      </span>
      <template v-else>
        <span class="grid-view__focus-badge-name">
          {{ activeName }}
        </span>
        <span v-if="overflowCount > 0" class="grid-view__focus-badge-count">
          +{{ overflowCount }}
        </span>
      </template>
    </div>
  </div>
</template>

<script>
import {
  ANONYMOUS_USER_ID,
  getAnonymousDisplayName,
} from '@baserow/modules/core/utils/presenceColors'
import { activeFocusEntry } from '@baserow/modules/database/utils/presenceFocusEntries'

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
    activeEntry() {
      return activeFocusEntry(this.entries)
    },
    isAnonymous() {
      return this.activeEntry?.user_id === ANONYMOUS_USER_ID
    },
    activeUser() {
      if (!this.activeEntry || this.isAnonymous) return null
      return this.$store.getters['workspace/getUserById'](
        this.activeEntry.user_id
      )
    },
    activeName() {
      if (this.isAnonymous) {
        return getAnonymousDisplayName(this.activeEntry.presence_id)
      }
      return this.activeUser ? this.activeUser.name : '?'
    },
    overflowCount() {
      return Math.max(0, this.entries.length - 1)
    },
    isEditing() {
      return Boolean(this.activeEntry && this.activeEntry.editing)
    },
    badgeStyle() {
      return {
        backgroundColor: this.activeEntry ? this.activeEntry.color : undefined,
        maxWidth: this.maxWidth + 'px',
      }
    },
  },
}
</script>
