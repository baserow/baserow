<template>
  <div class="select-application">
    <div v-if="loading" class="skeleton" aria-hidden="true">
      <SkeletonBlock
        v-for="index in 3"
        :key="`database-${index}`"
        width="220px"
        height="16px"
        class="margin-bottom-2"
      ></SkeletonBlock>
    </div>
    <template v-else-if="hasDatabases">
      <APIDocsSelectDatabaseWorkspace
        v-for="workspace in workspaces"
        :key="workspace.id"
        :workspace="workspace"
        :selected="selected"
      ></APIDocsSelectDatabaseWorkspace>
    </template>
    <p v-else class="margin-bottom-3">
      {{ $t('apiDocsSelectDatabase.needOneDatabase') }}
    </p>
  </div>
</template>

<script>
import { mapState } from 'vuex'

import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import APIDocsSelectDatabaseWorkspace from '@baserow/modules/database/components/docs/APIDocsSelectDatabaseWorkspace'

export default {
  name: 'APIDocsSelectDatabase',
  components: { APIDocsSelectDatabaseWorkspace },
  props: {
    selected: {
      type: Number,
      required: false,
      default: -1,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    hasDatabases() {
      const databaseType = DatabaseApplicationType.getType()
      return (
        this.$store.getters['application/getAll'].filter(
          (application) => application.type === databaseType
        ).length > 0
      )
    },
    ...mapState({
      workspaces: (state) => state.workspace.items,
    }),
  },
}
</script>
