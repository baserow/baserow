<template>
  <div class="agent-teams-cell">
    <Badge v-for="team in row.teams" :key="team.id" rounded size="large">{{
      team.name
    }}</Badge>
    <span v-if="!row.teams?.length" class="agent-teams-cell__empty">
      {{ $t('enterpriseAgents.noTeams') }}
    </span>
  </div>
</template>
<script>
export default {
  name: 'AgentTeamsCell',
  props: { row: { type: Object, required: true } },
}
</script>
