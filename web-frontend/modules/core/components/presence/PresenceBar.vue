<template>
  <div v-if="otherUsers.length > 0" class="presence-bar">
    <PresenceBadge
      v-for="user in visibleUsers"
      :key="
        user.user_id === ANONYMOUS_USER_ID ? user.presence_id : user.user_id
      "
      :user-id="user.user_id"
      :presence-id="user.presence_id"
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
import {
  ANONYMOUS_USER_ID,
  getAnonymousDisplayName,
} from '@baserow/modules/core/utils/presenceColors'
import { escapeHtml } from '@baserow/modules/core/utils/string'
import { getPresenceVisibleUsers } from '@baserow/modules/database/utils/presence'

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
    maxVisible() {
      return getPresenceVisibleUsers(this)
    },
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
      return this.otherUsers.slice(0, this.maxVisible)
    },
    overflowCount() {
      return Math.max(0, this.otherUsers.length - this.maxVisible)
    },
    overflowUsers() {
      return this.otherUsers.slice(this.maxVisible)
    },
    overflowTooltip() {
      return this.overflowUsers
        .map((u) => {
          let name
          if (u.user_id === ANONYMOUS_USER_ID) {
            name = getAnonymousDisplayName(u.presence_id)
          } else {
            const user = this.$store.getters['workspace/getUserById'](u.user_id)
            name = user ? user.name : 'Unknown'
          }
          return `<div class="presence-bar__tooltip-name">${escapeHtml(name)}</div>`
        })
        .join('')
    },
    tooltipOptions() {
      return {
        duration: 0.5,
        contentIsHtml: true,
        contentClasses: 'tooltip__content--expandable',
      }
    },
  },
}
</script>
