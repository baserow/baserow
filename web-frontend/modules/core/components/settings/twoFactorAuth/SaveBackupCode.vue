<template>
  <div class="save-backup-code">
    <p class="save-backup-code__description">
      If you lose access to your authenticator app or phone and can’t receive or
      generate authentication codes, you can use this backup. You can only use
      it once. Make sure you write it down or copy it into a safe place so that
      you can access it without logging in.
    </p>
    <div class="save-backup-code__subtitle">Backup codes</div>
    <div class="save-backup-code__code">
      <div v-for="code in backupCodes" :key="code">
        {{ code }}
      </div>
    </div>
    <div class="actions actions--right actions--gap">
      <Button type="secondary" icon="iconoir-copy" @click="copyToClipboard"
        >Copy</Button
      >
      <Button type="primary" @click="$emit('continue')">Continue</Button>
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
