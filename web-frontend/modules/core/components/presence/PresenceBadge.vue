<template>
  <div
    v-tooltip="displayName"
    class="avatar avatar--medium avatar--rounded presence-bar__avatar"
    :style="{ backgroundColor: color }"
  >
    {{ initials }}
  </div>
</template>

<script>
import {
  ANONYMOUS_USER_ID,
  getAnonymousDisplayName,
  getPresenceColor,
} from '@baserow/modules/core/utils/presenceColors'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

export default {
  name: 'PresenceBadge',
  props: {
    userId: {
      type: Number,
      required: true,
    },
    presenceId: {
      type: String,
      default: '',
    },
  },
  computed: {
    isAnonymous() {
      return this.userId === ANONYMOUS_USER_ID
    },
    user() {
      if (this.isAnonymous) return null
      return this.$store.getters['workspace/getUserById'](this.userId)
    },
    displayName() {
      if (this.isAnonymous) {
        return getAnonymousDisplayName(this.presenceId)
      }
      return this.user ? this.user.name : 'Unknown'
    },
    initials() {
      if (this.isAnonymous) return '?'
      if (!this.user) return '?'
      return nameAbbreviation(this.user.name)
    },
    color() {
      return getPresenceColor(this.userId, this.presenceId)
    },
  },
}
</script>
