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
      class="avatar avatar--medium avatar--rounded presence-bar__overflow"
    >
      +{{ overflowCount }}
    </div>
  </div>
</template>

<script>
import PresenceBadge from '@baserow/modules/core/components/presence/PresenceBadge'

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
          return user ? user.name : 'Unknown'
        })
        .join('\n')
    },
    tooltipOptions() {
      return {
        contentClasses:
          'tooltip__content--expandable tooltip__content--expandable-plain-text',
      }
    },
  },
}
</script>
