<template>
  <div class="select-members-list">
    <div>
      <FormInput
        v-model="activeSearchTerm"
        size="large"
        :placeholder="$t('selectAgentsList.searchPlaceholder')"
        @keyup="search(activeSearchTerm)"
      ></FormInput>

      <div class="margin-top-2">
        {{
          $t('selectAgentsList.selectedAmountLabel', {
            count: agentsSelected.length,
          })
        }}
      </div>
    </div>
    <List
      class="margin-top-2 select-members-list__items"
      :items="agentsFiltered"
      :selected-items="agentsSelected"
      :attributes="[]"
      selectable
      @selected="agentSelected"
    >
      <template #left-side="{ item }">
        <Avatar
          class="margin-left-1"
          rounded
          size="medium"
          :color="subjectType.avatarColor"
          :initials="nameAbbreviation(subjectType.getDisplayName(item))"
        ></Avatar>

        <span
          v-tooltip="subjectType.getDisplayName(item)"
          class="margin-left-1 select-members-list__user-name"
        >
          {{ subjectType.getDisplayName(item) }}
        </span>
      </template>
    </List>
    <SelectSubjectsListFooter
      class="margin-top-1"
      :subject-type="subjectType.type"
      :scope-type="scopeType"
      :count="agentsSelected.length"
      :show-role-selector="showRoleSelector"
      :show-commercial-info="false"
      @invite="$emit('invite', agentsSelected, $event)"
    />
  </div>
</template>

<script>
import SelectSubjectsListFooter from '@baserow_enterprise/components/rbac/SelectSubjectsListFooter'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

export default {
  name: 'SelectAgentsList',
  components: { SelectSubjectsListFooter },
  emits: ['invite'],
  props: {
    agents: {
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
      agentsFiltered: this.agents,
      agentsSelected: [],
      activeSearchTerm: null,
    }
  },
  computed: {
    subjectType() {
      return this.$registry.get('subject', 'core.Agent')
    },
  },
  methods: {
    search(value) {
      if (value === null || value === '' || this.agents.length === 0) {
        this.agentsFiltered = this.agents
      } else {
        const searchTerm = value.trim().toLowerCase()
        this.agentsFiltered = this.agents.filter((agent) =>
          agent.name.toLowerCase().includes(searchTerm)
        )
      }
    },
    agentSelected({ value, item }) {
      if (value) {
        this.agentsSelected.push(item)
      } else {
        const index = this.agentsSelected.findIndex(
          (agent) => agent.id === item.id
        )
        this.agentsSelected.splice(index, 1)
      }
    },
    nameAbbreviation,
  },
}
</script>
