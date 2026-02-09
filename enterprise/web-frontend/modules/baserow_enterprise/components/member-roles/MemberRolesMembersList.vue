<template>
  <div v-if="roleAssignmentsSorted.length === 0">
    {{ $t('memberRolesMembersList.noMembers') }}
  </div>
  <ul v-else class="list list margin-bottom-0">
    <li
      v-for="roleAssignment in roleAssignmentsSorted"
      :key="roleAssignment.subject.id"
      class="list__item"
    >
      <!-- User subjects -->
      <div
        v-if="roleAssignment.subject_type === 'auth.User'"
        class="member-roles-members-list__subject-section"
      >
        <Avatar
          size="large"
          :initials="nameAbbreviation(roleAssignment.subject.first_name)"
          rounded
        ></Avatar>

        <div
          v-tooltip="roleAssignment.subject.first_name"
          class="margin-left-1 member-roles-members-list__user-name"
        >
          {{ roleAssignment.subject.first_name }}
        </div>
      </div>

      <!-- Team subjects -->
      <div v-else class="member-roles-members-list__subject-section">
        <div class="member-roles-members-list__team-initials">
          {{ nameAbbreviation(roleAssignment.subject.name) }}
        </div>
        <div
          v-tooltip="roleAssignment.subject.name"
          class="margin-left-1 member-roles-members-list__team-name"
        >
          {{ roleAssignment.subject.name }}
          <div class="member-roles-members-list__team-member-count">
            {{
              $t('memberRolesMembersList.teamMembersCount', {
                count: getCount(roleAssignment.subject.id),
              })
            }}
          </div>
        </div>
      </div>
      <div class="member-roles-members-list__role-selector">
        <HelpIcon
          v-if="getRole(roleAssignment).uid === 'ADMIN'"
          class="margin-right-1"
          :tooltip="$t('memberRolesMembersList.adminHelpText')"
        />
        <RoleSelector
          :disabled="
            roleAssignment.subject.id === userId &&
            roleAssignment.subject_type === 'auth.User'
          "
          :roles="getAvailableRoles(roles)"
          :value="getRole(roleAssignment)"
          :allow-removing-role="true"
          :workspace="workspace"
          @delete="$emit('role-updated', roleAssignment, null)"
          @input="({ uid }) => $emit('role-updated', roleAssignment, uid)"
        />
      </div>
    </li>
  </ul>
</template>

<script>
import { mapGetters } from 'vuex'
import RoleSelector from '@baserow_enterprise/components/member-roles/RoleSelector'
import { filterRoles } from '@baserow_enterprise/utils/roles'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

export default {
  name: 'MemberRolesMembersList',
  emits: ['role-updated'],
  components: { RoleSelector },
  props: {
    roleAssignments: {
      type: Array,
      required: false,
      default: () => [],
    },
    scopeId: {
      type: Number,
      required: true,
    },
    scopeType: {
      type: String,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    teams: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
    roles() {
      return this.workspace._.roles
    },
    roleAssignmentsSorted() {
      return [...this.roleAssignments].sort((a, b) =>
        a.subject_type > b.subject_type ? 1 : -1
      )
    },
  },
  methods: {
    getRole(roleAssignment) {
      return this.roles.find((role) => role.uid === roleAssignment.role)
    },
    getCount(teamId) {
      return this.teams.find(({ id }) => id === teamId).subject_count
    },
    getAvailableRoles(roleAssignment) {
      return filterRoles(this.roles, {
        scopeType: this.scopeType,
        subjectType: roleAssignment.subject_type,
      })
    },
    nameAbbreviation,
  },
}
</script>
