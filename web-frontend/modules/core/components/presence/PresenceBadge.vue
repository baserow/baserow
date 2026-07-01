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
import { getPresenceUserColor } from '@baserow/modules/core/utils/presenceColors'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

export default {
  name: 'PresenceBadge',
  props: {
    userId: {
      type: Number,
      required: true,
    },
  },
  computed: {
    user() {
      return this.$store.getters['workspace/getUserById'](this.userId)
    },
    displayName() {
      return this.user ? this.user.name : 'Unknown'
    },
    initials() {
      if (!this.user) return '?'
      return nameAbbreviation(this.user.name)
    },
    color() {
      return getPresenceUserColor(this.userId)
    },
  },
}
</script>
