<template>
  <div class="save-backup-code">
    <p class="save-backup-code__description">
      If you lose access to your authenticator app or phone and can’t receive or
      generate authentication codes, you can use this backup. You can only use
      it once. Make sure you write it down or copy it into a safe place so that
      you can access it without logging in.
    </p>
    <div class="save-backup-code__subtitle">Backup code</div>
    <div class="save-backup-code__code">
      <div v-for="code in backupCodes" :key="code">
        {{ code }}
      </div>
    </div>
    <Button type="secondary" icon="iconoir-copy">Copy</Button>
  </div>
</template>

<script>
export default {
  name: 'SaveBackupCode',
  props: {
    backupCodes: {
      type: Array,
      required: true,
    },
  },
}
</script>
