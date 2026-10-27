<template>
  <div class="invite-list">
    <p v-if="rows.length === 0" class="invite-list__subtitle">
      {{ $t('shareScope.noInheritedAccess', { type: scopeTypeName }) }}
    </p>
    <ul v-else class="invite-list__items invite-list__items--scrollable">
      <li v-for="row in rows" :key="row.key" class="invite-list__item">
        <div class="invite-list__subject">
          <Avatar
            :initials="row.initials"
            :icon="row.initials ? '' : row.icon"
            size="large"
          />
          <div>
            <div class="invite-list__name">{{ row.name }}</div>
            <div class="invite-list__subtitle">
              <template v-for="(count, index) in row.counts" :key="count.key">
                <span v-if="index > 0"> • </span>
                {{ count.label }}
              </template>
            </div>
          </div>
        </div>
        <div>
          <a @click="toggleContext(row, $event.currentTarget)">
            {{ row.fromLabel }}
            <i class="iconoir-nav-arrow-down"></i>
          </a>
        </div>
      </li>
    </ul>
    <Context ref="context" class="scope-inherited-access__context">
      <template v-if="openRow">
        <p class="scope-inherited-access__explanation">
          {{ openRow.explanation }}
        </p>
        <ul
          v-if="openRow.scopeType === 'workspace' || openRow.canManage"
          class="context__menu"
        >
          <li class="context__menu-item context__menu-item--with-separator">
            <nuxt-link
              v-if="openRow.scopeType === 'workspace'"
              class="context__menu-item-link"
              :to="{
                name: 'settings-members',
                params: { workspaceId: workspace.id },
              }"
              @click="leave"
            >
              {{ $t('shareScope.manageWorkspaceRoles') }}
            </nuxt-link>
            <a v-else class="context__menu-item-link" @click="manage(openRow)">
              {{
                $t('shareScope.manageLevelRoles', { level: openRow.levelName })
              }}
            </a>
          </li>
        </ul>
      </template>
    </Context>
  </div>
</template>

<script>
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

/**
 * Who else reaches the object, summarised per level above it: the workspace,
 * and for a table or view the database, and for a view the table. A member or
 * agent is counted once, under the level their effective role comes from, so
 * whoever is blocked on a level above isn't counted at all. Those with a role on
 * the object itself, directly or through a team, are listed as direct access
 * instead, as are those whose own row there has no effect. Managing a level above
 * emits `navigate` with its target so the owning modal can replace its content.
 * Following the link to the workspace's members page emits `close`, as the
 * dialog has no place on that page.
 */
export default {
  name: 'ScopeInheritedAccess',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
    /**
     * The effective access of every member and agent with access to the object,
     * as returned by the effective access endpoint.
     */
    effectiveAccess: {
      type: Array,
      required: true,
    },
    /**
     * The keys of the subjects listed as direct access, which aren't counted.
     */
    directKeys: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['navigate', 'close'],
  data() {
    return {
      openRowKey: null,
    }
  },
  computed: {
    scopeTypeName() {
      return this.getLevelName(this.target.scopeType, this.target.scope)
    },
    /**
     * The levels above the object, from the workspace in.
     */
    levels() {
      const { database, table, scopeType } = this.target
      const levels = [
        {
          scopeType: 'workspace',
          scope: this.workspace,
          initials: nameAbbreviation(this.workspace.name),
          name: this.$t('shareScope.everyoneAt', { name: this.workspace.name }),
        },
      ]
      if (database && ['database_table', 'database_view'].includes(scopeType)) {
        levels.push({
          scopeType: 'application',
          scope: database,
          icon: 'iconoir-db',
          operation: 'application.read_role',
          manageTarget: {
            type: 'scope',
            scopeType: 'application',
            scope: database,
          },
        })
      }
      if (table && scopeType === 'database_view') {
        levels.push({
          scopeType: 'database_table',
          scope: table,
          icon: 'iconoir-table',
          operation: 'database.table.read_role',
          manageTarget: {
            type: 'scope',
            scopeType: 'database_table',
            scope: table,
            database,
          },
        })
      }
      return levels
    },
    enabledSubjectTypes() {
      return this.$registry
        .getOrderedList('subject')
        .filter((subjectType) => subjectType.isEnabled(this.workspace))
    },
    rows() {
      const roles = this.workspace._.roles.filter((role) => role.isVisible)
      return this.levels
        .map((level) => {
          const key = `${level.scopeType}:${level.scope.id}`
          const access = this.effectiveAccess.filter(
            (entry) =>
              entry.source_scope_type === level.scopeType &&
              entry.source_scope_id === level.scope.id &&
              !this.directKeys.includes(
                `${entry.subject_type}:${entry.subject_id}`
              )
          )
          const levelName = this.getLevelName(level.scopeType, level.scope)
          return {
            ...level,
            key,
            levelName,
            name:
              level.name ||
              this.$t('shareScope.everyoneWithRoleOn', {
                name: level.scope.name,
              }),
            counts: this.getCounts(access, roles),
            fromLabel:
              level.scopeType === 'workspace'
                ? this.$t('shareScope.fromWorkspace')
                : this.$t('shareScope.fromLevel', { level: levelName }),
            explanation:
              level.scopeType === 'workspace'
                ? this.$t('shareScope.fromWorkspaceExplanation', {
                    type: this.scopeTypeName,
                  })
                : this.$t('shareScope.fromLevelExplanation', {
                    type: this.scopeTypeName,
                    level: levelName,
                  }),
            canManage:
              Boolean(level.operation) &&
              this.$hasPermission(
                level.operation,
                level.scope,
                this.workspace.id
              ),
          }
        })
        .filter((row) => row.counts.length > 0)
    },
    openRow() {
      return this.rows.find((row) => row.key === this.openRowKey) || null
    },
  },
  methods: {
    getLevelName(scopeType, scope) {
      if (scopeType === 'workspace') {
        return this.$t('common.workspace').toLowerCase()
      }
      return this.targetType.getScopeTypeName(scopeType, scope).toLowerCase()
    },
    /**
     * Counts the members per role, then the agents per role, of the enabled
     * subject types, in the order of the roles.
     */
    getCounts(access, roles) {
      const counts = []
      for (const subjectType of this.enabledSubjectTypes) {
        const perRole = {}
        for (const entry of access) {
          if (entry.subject_type === subjectType.type) {
            perRole[entry.role] = (perRole[entry.role] || 0) + 1
          }
        }
        for (const role of roles) {
          const count = perRole[role.uid]
          if (!count) {
            continue
          }
          counts.push({
            key: `${subjectType.type}:${role.uid}`,
            label: subjectType.isUser()
              ? this.$t('shareScope.roleCount', { count, role: role.name })
              : this.$t(
                  'shareScope.agentRoleCount',
                  { count, role: role.name },
                  count
                ),
          })
        }
      }
      return counts
    },
    toggleContext(row, element) {
      this.openRowKey = row.key
      this.$refs.context.toggle(element, 'bottom', 'right', 4)
    },
    leave() {
      this.$refs.context.hide()
      this.$emit('close')
    },
    manage(row) {
      this.$refs.context.hide()
      this.$emit('navigate', row.manageTarget)
    },
  },
}
</script>
