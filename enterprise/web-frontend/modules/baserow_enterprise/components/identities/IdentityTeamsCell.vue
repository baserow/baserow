<template>
  <div class="identity-teams-cell">
    <Badge v-for="team in row.teams" :key="team.id" rounded size="large">{{
      team.name
    }}</Badge>
    <span v-if="!row.teams?.length" class="identity-teams-cell__empty">
      {{ $t('enterpriseIdentities.noTeams') }}
    </span>
  </div>
</template>
<script>
export default {
  name: 'IdentityTeamsCell',
  props: { row: { type: Object, required: true } },
}
</script>
