<template>
  <tr v-if="loading" class="data-table__table-row">
    <td :colspan="columns.length" class="data-table__table-cell">
      <div class="data-table__table-cell-content">
        <div class="loading"></div>
      </div>
    </td>
  </tr>
  <template v-else>
    <tr
      v-for="item in items"
      :key="item.key"
      class="data-table__table-row subject-role-assignments__row"
    >
      <td :colspan="roleColumnIndex" class="data-table__table-cell">
        <div
          class="data-table__table-cell-content subject-role-assignments__object"
        >
          <Avatar
            :icon="item.icon"
            color="neutral"
            size="large"
            rounded
            class="subject-role-assignments__icon"
          />
          <span class="subject-role-assignments__name">{{ item.name }}</span>
          <span class="subject-role-assignments__separator" aria-hidden="true"
            >·</span
          >
          <span class="subject-role-assignments__location">{{
            item.location
          }}</span>
        </div>
      </td>
      <td class="data-table__table-cell">
        <div
          class="data-table__table-cell-content subject-role-assignments__role"
        >
          <RoleSelectorButton
            :icon="item.role?.icon"
            :role-name="item.role?.name || item.roleUid"
            :read-only="!item.canChangeRole"
            @click="openRoleContext(item, $event)"
          />
          <HelpIcon
            v-if="item.helpText"
            :tooltip="item.helpText"
            :tooltip-content-classes="[
              'tooltip__content--expandable',
              'tooltip__content--expandable-plain-text',
            ]"
          />
        </div>
      </td>
      <td
        v-for="column in middleColumns"
        :key="column.key"
        class="data-table__table-cell"
      >
        <div class="data-table__table-cell-content"></div>
      </td>
      <td
        class="data-table__table-cell"
        :class="{ 'data-table__table-cell--sticky-right': lastColumnSticky }"
      >
        <div class="data-table__table-cell-content">
          <ButtonText
            v-if="item.canRemove"
            type="secondary"
            icon="iconoir-cancel"
            class="subject-role-assignments__remove"
            :aria-label="
              $t('subjectRoleAssignments.remove', { name: item.name })
            "
            @click="remove(item)"
          />
        </div>
      </td>
    </tr>
    <tr v-if="items.length < count" class="data-table__table-row">
      <td :colspan="columns.length" class="data-table__table-cell">
        <div class="data-table__table-cell-content">
          <div v-if="loadingMore" class="loading"></div>
          <a v-else class="subject-role-assignments__more" @click="loadMore">
            {{
              $t(
                'subjectRoleAssignments.showMore',
                { count: count - items.length },
                count - items.length
              )
            }}
          </a>
        </div>
      </td>
    </tr>
  </template>
  <EditRoleContext
    ref="roleContext"
    :workspace="workspace"
    :subject="editing || {}"
    :roles="editingRoles"
    role-value-column="role"
    @update-role="({ uid }) => changeRole(editing, uid)"
  />
  <ScopeNoAccessModal ref="noAccessModal" />
</template>

<script>
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ScopeNoAccessModal from '@baserow_enterprise/components/invitation/ScopeNoAccessModal'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import { filterRoles } from '@baserow_enterprise/utils/roles'

const PAGE_SIZE = 10

const UPDATE_ROLE_OPERATIONS = {
  application: 'application.update_role',
  database_table: 'database.table.update_role',
  database_view: 'database.table.view.update_role',
}

/**
 * The roles a member, team or agent holds on databases, tables and views, as rows
 * below their row in the members, teams or agents table. Fetched when the row is
 * expanded, a page at a time. Every role can be changed and removed by who may
 * manage the roles of its object. A role that has no effect, because the subject
 * is an admin of the workspace or of a database or table it is in, shows as a
 * locked admin role that can only be removed. The current user's own roles can't
 * be changed, as nobody can change their own role. Changing the subject's
 * workspace role reloads the roles, as it decides which ones are locked.
 */
export default {
  name: 'SubjectRoleAssignmentRows',
  components: { EditRoleContext, RoleSelectorButton, ScopeNoAccessModal },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    columns: {
      type: Array,
      required: true,
    },
    /**
     * Merges the given values into the table row, as provided by CrudTable.
     */
    updateRow: {
      type: Function,
      required: true,
    },
    subjectType: {
      type: String,
      required: true,
    },
    subjectId: {
      type: Number,
      required: true,
    },
    /**
     * The key of the column the role of every row is shown in.
     */
    roleColumnKey: {
      type: String,
      required: true,
    },
    /**
     * Whether the roles can't be changed, the current user's own for instance.
     */
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      loading: true,
      loadingMore: false,
      roleAssignments: [],
      count: 0,
      editing: null,
      // Counts the reloads, so only the latest one applies.
      reloadRequest: 0,
    }
  },
  computed: {
    workspaceRoleUid() {
      return this.row[this.roleColumnKey]
    },
    roleColumnIndex() {
      return Math.max(
        1,
        this.columns.findIndex(({ key }) => key === this.roleColumnKey)
      )
    },
    middleColumns() {
      return this.columns.slice(this.roleColumnIndex + 1, -1)
    },
    lastColumnSticky() {
      return Boolean(this.columns[this.columns.length - 1]?.stickyRight)
    },
    adminRole() {
      return this.workspace._.roles.find(({ uid }) => uid === 'ADMIN')
    },
    items() {
      return this.roleAssignments.map((roleAssignment) => {
        const locked = roleAssignment.locked_by !== null
        const canManage =
          !this.readOnly &&
          this.$hasPermission(
            UPDATE_ROLE_OPERATIONS[roleAssignment.scope_type],
            { id: roleAssignment.scope_id },
            this.workspace.id
          )
        return {
          key: `${roleAssignment.scope_type}:${roleAssignment.scope_id}`,
          roleAssignment,
          name: roleAssignment.name,
          icon: this.getIcon(roleAssignment),
          location: this.getLocation(roleAssignment),
          roleUid: roleAssignment.role,
          role: locked
            ? this.adminRole
            : this.workspace._.roles.find(
                ({ uid }) => uid === roleAssignment.role
              ),
          canChangeRole: canManage && !locked,
          canRemove: canManage,
          helpText: locked ? this.getLockedHelpText(roleAssignment) : null,
        }
      })
    },
    editingRoles() {
      return this.editing
        ? filterRoles(this.workspace._.roles, {
            scopeType: this.editing.roleAssignment.scope_type,
          })
        : []
    },
  },
  watch: {
    /**
     * The subject's workspace role decides which roles are locked by it.
     */
    workspaceRoleUid() {
      this.reload()
    },
  },
  async mounted() {
    try {
      await this.fetchPage()
    } finally {
      this.loading = false
    }
  },
  methods: {
    async fetchPage() {
      try {
        const data = await this.fetchRoleAssignments(
          this.roleAssignments.length,
          PAGE_SIZE
        )
        this.roleAssignments = this.roleAssignments.concat(data.results)
        this.count = data.count
        this.syncCount()
      } catch (error) {
        notifyIf(error)
      }
    },
    /**
     * Fetches the roles loaded so far again, replacing them once they arrive. The
     * response of an older reload is ignored once a newer one was made.
     */
    async reload() {
      const request = ++this.reloadRequest
      try {
        const data = await this.fetchRoleAssignments(
          0,
          Math.max(PAGE_SIZE, this.roleAssignments.length)
        )
        if (request === this.reloadRequest) {
          this.roleAssignments = data.results
          this.count = data.count
          this.syncCount()
        }
      } catch (error) {
        if (request === this.reloadRequest) {
          notifyIf(error)
        }
      }
    },
    async fetchRoleAssignments(offset, limit) {
      const { data } = await RoleAssignmentsService(
        this.$client
      ).getSubjectRoleAssignments(
        this.workspace.id,
        this.subjectType,
        this.subjectId,
        { offset, limit }
      )
      return data
    },
    async loadMore() {
      this.loadingMore = true
      try {
        await this.fetchPage()
      } finally {
        this.loadingMore = false
      }
    },
    /**
     * Keeps the count shown in the table row in line with the listed roles.
     */
    syncCount() {
      if (this.row.role_assignment_count !== this.count) {
        this.updateRow({ ...this.row, role_assignment_count: this.count })
      }
    },
    getScopeTypeName(scopeType, type) {
      if (scopeType === 'application') {
        return (
          this.$registry.get('application', type)?.getName() ||
          this.$t('subjectRoleAssignments.application')
        )
      }
      if (scopeType === 'database_table') {
        return this.$t('subjectRoleAssignments.table')
      }
      if (scopeType === 'database_view') {
        return this.$t('subjectRoleAssignments.view')
      }
      return this.$t('common.workspace')
    },
    getIcon({ scope_type: scopeType, type }) {
      if (scopeType === 'application') {
        return (
          this.$registry.get('application', type)?.iconClass || 'iconoir-db'
        )
      }
      if (scopeType === 'database_view') {
        return this.$registry.get('view', type)?.iconClass || 'iconoir-eye'
      }
      return 'iconoir-table'
    },
    /**
     * Where the object is, for example "Table in Projects" or "View in Projects /
     * Tasks", or "Database in <workspace>" for an application.
     */
    getLocation(roleAssignment) {
      const path =
        roleAssignment.parents.length > 0
          ? roleAssignment.parents.map(({ name }) => name).join(' / ')
          : this.workspace.name
      return this.$t('subjectRoleAssignments.location', {
        type: this.getScopeTypeName(
          roleAssignment.scope_type,
          roleAssignment.type
        ),
        path,
      })
    },
    /**
     * Explains that the subject is an admin of a level above the object, which
     * makes the role have no effect. A database is the only application that
     * contains other objects.
     */
    getLockedHelpText({ scope_type: scopeType, type, locked_by: lockedBy }) {
      const level =
        lockedBy.scope_type === 'application'
          ? this.getScopeTypeName('application', 'database')
          : this.getScopeTypeName(lockedBy.scope_type)
      return this.$t('shareScope.inheritedAdminHelpText', {
        level: level.toLowerCase(),
        type: this.getScopeTypeName(scopeType, type).toLowerCase(),
      })
    },
    openRoleContext(item, event) {
      this.editing = { ...item, role: item.roleUid }
      this.$refs.roleContext.toggle(event.currentTarget, 'bottom', 'left', 4)
    },
    async changeRole(item, roleUid) {
      this.$refs.roleContext.hide()
      if (
        roleUid === 'NO_ACCESS' &&
        !(await this.$refs.noAccessModal.ask(
          this.$t('shareScope.noAccessDescription', {
            name: item.name,
            type: this.getScopeTypeName(
              item.roleAssignment.scope_type,
              item.roleAssignment.type
            ).toLowerCase(),
          })
        ))
      ) {
        return
      }
      await this.save(item.roleAssignment, roleUid)
    },
    remove(item) {
      return this.save(item.roleAssignment, null)
    },
    /**
     * Changes the role on the object, or removes it when `roleUid` is null, and
     * restores the previous state if that fails.
     */
    async save(roleAssignment, roleUid) {
      const index = this.roleAssignments.indexOf(roleAssignment)
      if (index === -1) {
        return
      }
      if (roleUid === null) {
        this.roleAssignments.splice(index, 1)
        this.count -= 1
      } else {
        this.roleAssignments.splice(index, 1, {
          ...roleAssignment,
          role: roleUid,
        })
      }
      this.syncCount()

      try {
        await RoleAssignmentsService(this.$client).assignRole(
          this.subjectId,
          this.subjectType,
          this.workspace.id,
          roleAssignment.scope_id,
          roleAssignment.scope_type,
          roleUid
        )
      } catch (error) {
        if (roleUid === null) {
          this.roleAssignments.splice(index, 0, roleAssignment)
          this.count += 1
        } else {
          this.roleAssignments.splice(index, 1, roleAssignment)
        }
        this.syncCount()
        notifyIf(error)
      }
    },
  },
}
</script>
