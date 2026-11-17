<template>
  <span>{{ message }}</span>
</template>

<script>
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export default {
  name: 'SnapshotModalWarning',
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  computed: {
    message() {
      // Roles can be given on a database's tables and views too. Every other
      // application type only has roles on the application itself.
      if (this.application.type === DatabaseApplicationType.getType()) {
        return this.$t('snapshotModalWarning.messageDatabase')
      }
      return this.$t('snapshotModalWarning.messageApplication', {
        applicationTypeName: this.$registry
          .get('application', this.application.type)
          .getName()
          .toLowerCase(),
      })
    },
  },
}
</script>
