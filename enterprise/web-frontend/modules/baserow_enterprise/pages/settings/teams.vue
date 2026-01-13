<template>
  <TeamsTable :workspace="workspace" />
</template>

<script>
import TeamsTable from '@baserow_enterprise/components/teams/TeamsTable'
import { ENTERPRISE_ACTION_SCOPES } from '@baserow_enterprise/undoRedoConstants'

export default {
  name: 'Teams',
  components: { TeamsTable },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  mounted() {
    this.$store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      ENTERPRISE_ACTION_SCOPES.teams_in_workspace(this.workspace.id)
    )
  },
  beforeUnmount() {
    this.$store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      ENTERPRISE_ACTION_SCOPES.teams_in_workspace(null)
    )
  },
}
</script>
