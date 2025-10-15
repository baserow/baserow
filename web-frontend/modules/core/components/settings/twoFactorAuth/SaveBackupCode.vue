<template>
  <div class="save-backup-code">
    <p class="save-backup-code__description">
      {{ $t('saveBackupCode.description') }}
    </p>
    <div class="save-backup-code__subtitle">
      {{ $t('saveBackupCode.backupCodes') }}
    </div>
    <div class="save-backup-code__code">
      <div v-for="code in backupCodes" :key="code">
        {{ code }}
      </div>
    </div>
    <div class="actions actions--right actions--gap">
      <Button type="secondary" icon="iconoir-copy" @click="copyToClipboard">{{
        $t('saveBackupCode.copy')
      }}</Button>
      <Button type="primary" @click="$emit('continue')">{{
        $t('saveBackupCode.continue')
      }}</Button>
    </div>
  </div>
</template>

<script>
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'SaveBackupCode',
  props: {
    backupCodes: {
      type: Array,
      required: true,
    },
  },
  computed: {
    backupCodesAsText() {
      return this.backupCodes.join('\n')
    },
  },
  methods: {
    copyToClipboard() {
      copyToClipboard(this.backupCodesAsText)
      this.$store.dispatch('toast/success', {
        title: this.$t('saveBackupCode.backupCodesCopiedTitle'),
        message: this.$t('saveBackupCode.backupCodesCopiedMessage'),
      })
    },
  },
}
</script>
