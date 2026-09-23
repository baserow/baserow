<template>
  <Modal ref="modal" :small="true" :full-height="true">
    <Tabs no-padding class="role-assignment-model__full-height-tabs">
      <Tab
        :title="$t('roleAssignmentModal.membersTab')"
        class="role-assignment-model__full-height-tab"
      >
        <SelectMembersList
          :users="users"
          :scope-type="scopeType"
          show-role-selector
          @invite="(...params) => onInvite('invite-members', ...params)"
        />
      </Tab>
      <Tab
        v-if="agentsEnabled"
        :title="$t('roleAssignmentModal.agentsTab')"
        class="role-assignment-model__full-height-tab"
      >
        <SelectAgentsList
          :agents="agents"
          :scope-type="scopeType"
          show-role-selector
          @invite="(...params) => onInvite('invite-agents', ...params)"
        />
      </Tab>
      <Tab
        :title="$t('roleAssignmentModal.teamsTab')"
        class="role-assignment-model__full-height-tab"
      >
        <SelectTeamsList
          :teams="teams"
          :scope-type="scopeType"
          show-role-selector
          @invite="(...params) => onInvite('invite-teams', ...params)"
        />
      </Tab>
    </Tabs>
  </Modal>
</template>

<script>
import Modal from '@baserow/modules/core/mixins/modal'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import SelectMembersList from '@baserow_enterprise/components/rbac/SelectMembersList'
import SelectTeamsList from '@baserow_enterprise/components/rbac/SelectTeamsList'
import SelectAgentsList from '@baserow_enterprise/components/rbac/SelectAgentsList'

export default {
  name: 'RoleAssignmentModal',
  components: { SelectTeamsList, SelectAgentsList, SelectMembersList },
  mixins: [Modal],
  props: {
    users: {
      type: Array,
      required: false,
      default: () => [],
    },
    teams: {
      type: Array,
      required: false,
      default: () => [],
    },
    agents: {
      type: Array,
      required: false,
      default: () => [],
    },
    scopeType: {
      type: String,
      required: true,
    },
  },
  computed: {
    agentsEnabled() {
      return this.$featureFlagIsEnabled(FF_AGENTS)
    },
  },
  methods: {
    onInvite(eventName, ...params) {
      this.$emit(eventName, ...params)
      this.hide()
    },
  },
}
</script>
