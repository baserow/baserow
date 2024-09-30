<template>
  <ModalV2 size="small" full-height :header="false">
    <template #content>
      <Tabs full-height @update:selectedIndex="handleTabUpdate">
        <Tab
          :title="$t('roleAssignmentModal.membersTab')"
          @update="selectedTab = $event"
        >
          <SelectMembersList
            :users="users"
            :scope-type="scopeType"
            show-role-selector
            :users-selected.sync="membersSelected"
          />
        </Tab>
        <Tab :title="$t('roleAssignmentModal.teamsTab')">
          <SelectTeamsList
            :teams="teams"
            :scope-type="scopeType"
            show-role-selector
            :teams-selected.sync="teamsSelected"
          />
        </Tab>
      </Tabs>
    </template>

    <template #footer-content>
      <SelectSubjectsListFooter
        :subject-type="subjectType"
        :scope-type="scopeType"
        :count="getCount()"
        show-role-selector
        @invite="handleInvite"
      />
    </template>
  </ModalV2>
</template>

<script>
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import SelectMembersList from '@baserow_enterprise/components/rbac/SelectMembersList'
import SelectSubjectsListFooter from '@baserow_enterprise/components/rbac/SelectSubjectsListFooter'
import SelectTeamsList from '@baserow_enterprise/components/rbac/SelectTeamsList'

export default {
  name: 'RoleAssignmentModal',
  components: {
    SelectTeamsList,
    SelectMembersList,
    SelectSubjectsListFooter,
  },
  mixins: [modalv2],
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
    scopeType: {
      type: String,
      required: true,
    },
    showRoleSelector: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      membersSelected: [],
      teamsSelected: [],
      selectedTab: 'members',
      subjectType: 'auth.User',
      eventName: 'invite-members',
    }
  },
  watch: {
    selectedTab(newVal) {
      if (newVal === 'members') {
        this.subjectType = 'auth.User'
        this.eventName = 'invite-members'
      } else if (newVal === 'teams') {
        this.subjectType = 'baserow_enterprise.Team'
        this.eventName = 'invite-teams'
      }
    },
  },
  methods: {
    handleInvite(role) {
      this.$emit(this.eventName, this[`${this.selectedTab}Selected`], role)
      this.hide()
    },
    handleTabUpdate(index) {
      switch (index) {
        case 0:
          this.selectedTab = 'members'
          break
        case 1:
          this.selectedTab = 'teams'
          break
        default:
          this.selectedTab = 'members'
      }
    },
    getCount() {
      return this.selectedTab === 'members'
        ? this.membersSelected.length
        : this.teamsSelected.length
    },
  },
}
</script>
