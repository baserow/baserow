<template>
  <FormGroup :label="$t('enterpriseAgents.teams')" class="margin-top-2">
    <div v-if="loading" class="loading"></div>
    <div v-else class="agent-teams-form-field">
      <span v-if="teams.length === 0" class="agent-teams-form-field__empty">
        {{ $t('enterpriseAgents.noTeams') }}
      </span>
      <RadioButton
        v-for="team in teams"
        :key="team.id"
        :model-value="selectedTeamIds.includes(team.id)"
        :value="true"
        :deselected-value="false"
        :icon="
          selectedTeamIds.includes(team.id) ? 'iconoir-check' : 'iconoir-plus'
        "
        allow-deselect
        @update:model-value="toggle(team.id, $event)"
      >
        {{ team.name }}
      </RadioButton>
    </div>
  </FormGroup>
</template>

<script>
import TeamService from '@baserow_enterprise/services/team'

export default {
  name: 'AgentTeamsFormField',
  props: {
    modelValue: { type: Object, required: true },
    workspace: { type: Object, required: true },
    agent: { type: Object, default: null },
    roles: { type: Array, default: () => [] },
  },
  emits: ['update:modelValue'],
  data() {
    return { loading: true, teams: [] }
  },
  computed: {
    selectedTeamIds() {
      return Array.isArray(this.modelValue.team_ids)
        ? this.modelValue.team_ids
        : []
    },
  },
  async mounted() {
    const { data } = await TeamService(this.$client).fetchAll(this.workspace.id)
    this.teams = data.results || data
    this.loading = false
  },
  methods: {
    toggle(teamId, selected) {
      const ids = new Set(this.selectedTeamIds)
      if (selected) {
        ids.add(teamId)
      } else {
        ids.delete(teamId)
      }
      this.$emit('update:modelValue', {
        ...this.modelValue,
        team_ids: [...ids],
      })
    },
  },
}
</script>
