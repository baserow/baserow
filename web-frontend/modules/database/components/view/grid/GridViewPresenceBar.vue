<template>
  <div v-if="allUsers.length > 0" class="presence-bar">
    <div
      v-for="user in visibleUsers"
      :key="user.user_id"
      class="avatar avatar--large avatar--rounded presence-bar__avatar"
      :style="{ backgroundColor: getColor(user.user_id) }"
      :title="getDisplayName(user.user_id)"
    >
      {{ getInitials(user.user_id) }}
    </div>
    <div
      v-if="overflowCount > 0"
      class="avatar avatar--large avatar--rounded presence-bar__overflow"
    >
      +{{ overflowCount }}
    </div>
  </div>
</template>

<script>
import { getPresenceUserColor } from '@baserow/modules/core/utils/presenceColors'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

const MAX_VISIBLE = 3

export default {
  name: 'GridViewPresenceBar',
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
    allUsers() {
      if (!this.spaceName) return []
      const self = { user_id: this.currentUserId }
      const others = this.remoteUsers.filter(
        (u) => u.user_id !== this.currentUserId
      )
      return [self, ...others]
    },
    visibleUsers() {
      return this.allUsers.slice(0, MAX_VISIBLE)
    },
    overflowCount() {
      return Math.max(0, this.allUsers.length - MAX_VISIBLE)
    },
  },
  methods: {
    getColor(userId) {
      return getPresenceUserColor(userId)
    },
    getDisplayName(userId) {
      const user = this.$store.getters['workspace/getUserById'](userId)
      return user ? user.name : 'Unknown'
    },
    getInitials(userId) {
      const user = this.$store.getters['workspace/getUserById'](userId)
      if (!user) return '?'
      return nameAbbreviation(user.name)
    },
  },
}
</script>
