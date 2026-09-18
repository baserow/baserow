<template>
  <FormGroup :label="$t('enterpriseAgents.teams')" class="margin-top-2">
    <div v-if="loading" class="loading"></div>
    <Alert v-else-if="loadError" type="error">
      <template #title>{{ $t('enterpriseAgents.teamsLoadError') }}</template>
      <p>{{ $t('enterpriseAgents.teamsLoadErrorDescription') }}</p>
      <Button type="secondary" @click="fetchTeams">
        {{ $t('enterpriseAgents.retry') }}
      </Button>
    </Alert>
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
    return { loading: true, loadError: false, teams: [] }
  },
  computed: {
    selectedTeamIds() {
      return Array.isArray(this.modelValue.team_ids)
        ? this.modelValue.team_ids
        : []
    },
  },
  mounted() {
    this.fetchTeams()
  },
  methods: {
    async fetchTeams() {
      this.loading = true
      this.loadError = false
      try {
        const { data } = await TeamService(this.$client).fetchAll(
          this.workspace.id
        )
        this.teams = data.results || data
      } catch {
        this.loadError = true
      } finally {
        this.loading = false
      }
    },
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
