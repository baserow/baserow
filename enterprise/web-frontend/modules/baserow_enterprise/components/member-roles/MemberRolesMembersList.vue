<template>
  <div v-if="roleAssignmentsSorted.length === 0">
    {{ $t('memberRolesMembersList.noMembers') }}
  </div>
  <ul v-else class="list list margin-bottom-0">
    <li
      v-for="roleAssignment in roleAssignmentsSorted"
      :key="`${roleAssignment.subject_type}:${roleAssignment.subject.id}`"
      class="list__item"
    >
      <div
        v-if="!hasSubjectCount(roleAssignment.subject)"
        class="member-roles-members-list__subject-section"
      >
        <Avatar
          size="large"
          :initials="nameAbbreviation(getDisplayName(roleAssignment))"
          :color="getSubjectType(roleAssignment).avatarColor"
          rounded
        ></Avatar>

        <div
          v-tooltip="getDisplayName(roleAssignment)"
          class="margin-left-1 member-roles-members-list__user-name"
        >
          {{ getDisplayName(roleAssignment) }}
        </div>
      </div>

      <!-- Team subjects -->
      <div v-else class="member-roles-members-list__subject-section">
        <div class="member-roles-members-list__team-initials">
          {{ nameAbbreviation(getDisplayName(roleAssignment)) }}
        </div>
        <div
          v-tooltip="getDisplayName(roleAssignment)"
          class="margin-left-1 member-roles-members-list__team-name"
        >
          {{ getDisplayName(roleAssignment) }}
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
          v-if="getInheritedAdminLevel(roleAssignment)"
          class="margin-right-1"
          :tooltip="
            $t('memberRolesMembersList.inheritedAdminHelpText', {
              type: scopeTypeName,
              level: getInheritedAdminLevel(roleAssignment),
            })
          "
        />
        <HelpIcon
          v-else-if="
            getRole(roleAssignment).uid === 'ADMIN' &&
            scopeType !== 'database_view'
          "
          class="margin-right-1"
          :tooltip="
            $t('memberRolesMembersList.scopeAdminHelpText', {
              type: scopeTypeName,
            })
          "
        />
        <RoleSelector
          :disabled="
            getSubjectType(roleAssignment).isCurrentUser(
              roleAssignment.subject,
              userId
            )
          "
          :roles="
            getInheritedAdminLevel(roleAssignment)
              ? [adminRole]
              : getAvailableRoles(roles)
          "
          :value="
            getInheritedAdminLevel(roleAssignment)
              ? adminRole
              : getRole(roleAssignment)
          "
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
    /**
     * The lower case label of the scope, used in the explanations.
     */
    scopeTypeName: {
      type: String,
      required: false,
      default: '',
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
    /**
     * The subjects that are an admin of the workspace or of a scope above this
     * one, as `{ '<subject type>:<id>': '<scope label>' }`. Their role here has
     * no effect, so they are shown as admins with a locked role.
     */
    inheritedAdmins: {
      type: Object,
      required: false,
      default: () => ({}),
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
    adminRole() {
      return this.roles.find((role) => role.uid === 'ADMIN')
    },
    roleAssignmentsSorted() {
      return [...this.roleAssignments].sort((a, b) =>
        a.subject_type > b.subject_type ? 1 : -1
      )
    },
  },
  methods: {
    getSubjectType(roleAssignment) {
      return this.$registry.get('subject', roleAssignment.subject_type)
    },
    getDisplayName(roleAssignment) {
      return this.getSubjectType(roleAssignment).getDisplayName(
        roleAssignment.subject
      )
    },
    hasSubjectCount(subject) {
      return subject.subject_count !== undefined
    },
    getRole(roleAssignment) {
      return this.roles.find((role) => role.uid === roleAssignment.role)
    },
    getInheritedAdminLevel(roleAssignment) {
      const key = this.getSubjectType(roleAssignment).getKey(
        roleAssignment.subject
      )
      return this.inheritedAdmins[key] || null
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
