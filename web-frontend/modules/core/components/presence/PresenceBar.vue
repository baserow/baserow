<template>
  <div v-if="otherUsers.length > 0" class="presence-bar">
    <PresenceBadge
      v-for="user in visibleUsers"
      :key="user.user_id"
      :user-id="user.user_id"
    />
    <div
      v-if="overflowCount > 0"
      v-tooltip:[tooltipOptions]="overflowTooltip"
      tooltip-position="bottom-left"
      class="avatar avatar--medium avatar--rounded presence-bar__overflow"
    >
      +{{ overflowCount }}
    </div>
  </div>
</template>

<script>
import PresenceBadge from '@baserow/modules/core/components/presence/PresenceBadge'
import { escapeHtml } from '@baserow/modules/core/utils/string'

const MAX_VISIBLE = 3

export default {
  name: 'PresenceBar',
  components: {
    PresenceBadge,
  },
  props: {
    spaceName: {
      type: String,
      default: '',
    },
  },
  computed: {
    currentUserId() {
      return this.$store.getters['auth/getUserId']
    },
    remoteUsers() {
      if (!this.spaceName) return []
      return this.$store.getters['presence/getUniqueUsersBySpace'](
        this.spaceName
      )
    },
    otherUsers() {
      return this.remoteUsers.filter((u) => u.user_id !== this.currentUserId)
    },
    visibleUsers() {
      return this.otherUsers.slice(0, MAX_VISIBLE)
    },
    overflowCount() {
      return Math.max(0, this.otherUsers.length - MAX_VISIBLE)
    },
    overflowUsers() {
      return this.otherUsers.slice(MAX_VISIBLE)
    },
    overflowTooltip() {
      return this.overflowUsers
        .map((u) => {
          const user = this.$store.getters['workspace/getUserById'](u.user_id)
          const name = user ? user.name : 'Unknown'
          return `<div class="presence-bar__tooltip-name">${escapeHtml(name)}</div>`
        })
        .join('')
    },
    tooltipOptions() {
      return {
        contentIsHtml: true,
        contentClasses:
          'tooltip__content--expandable tooltip__content--expandable-plain-text',
      }
    },
  },
}
</script>
