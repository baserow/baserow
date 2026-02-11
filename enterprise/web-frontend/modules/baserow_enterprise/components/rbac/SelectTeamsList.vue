<template>
  <div class="select-members-list">
    <div>
      <FormInput
        v-model="activeSearchTerm"
        size="large"
        :placeholder="$t('selectTeamsList.searchPlaceholder')"
        @keyup="search(activeSearchTerm)"
      ></FormInput>

      <div class="margin-top-2">
        {{
          $t('selectTeamsList.selectedAmountLabel', {
            count: teamsSelected.length,
          })
        }}
      </div>
    </div>
    <List
      class="margin-top-2 select-teams-list__items"
      :items="teamsFiltered"
      :selected-items="teamsSelected"
      :attributes="[]"
      selectable
      @selected="teamSelected"
    >
      <template #left-side="{ item }">
        <span
          v-tooltip="item.name"
          class="margin-left-1 select-teams-list__team-name"
        >
          {{ item.name }}
        </span>
      </template>
    </List>
    <SelectSubjectsListFooter
      class="margin-top-1"
      subject-type="baserow_enterprise.Team"
      :scope-type="scopeType"
      :count="teamsSelected.length"
      :show-role-selector="showRoleSelector"
      @invite="$emit('invite', teamsSelected, $event)"
    />
  </div>
</template>

<script>
import SelectSubjectsListFooter from '@baserow_enterprise/components/rbac/SelectSubjectsListFooter'
export default {
  name: 'SelectTeamsList',
  emits: ['invite'],
  components: { SelectSubjectsListFooter },
  props: {
    teams: {
      type: Array,
      required: false,
      default: () => [],
    },
    showRoleSelector: {
      type: Boolean,
      default: false,
    },
    scopeType: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      teamsFiltered: this.teams,
      teamsSelected: [],
      activeSearchTerm: null,
    }
  },
  computed: {
    searchAbleAttributes() {
      return ['name']
    },
  },
  methods: {
    search(value) {
      if (value === null || value === '' || this.teams.length === 0) {
        this.teamsFiltered = this.teams
      } else {
        const valueSanitised = value.trim().toLowerCase()
        this.teamsFiltered = this.teams.filter((team) =>
          this.searchAbleAttributes.some((attribute) =>
            team[attribute].toLowerCase().includes(valueSanitised)
          )
        )
      }
    },
    teamSelected({ value, item }) {
      if (value) {
        this.teamsSelected.push(item)
      } else {
        const index = this.teamsSelected.findIndex(
          (team) => team.id === item.id
        )
        this.teamsSelected.splice(index, 1)
      }
    },
  },
}
</script>
