<template>
  <div class="invite-list">
    <div v-if="items.length === 0" class="invite-list__empty">
      <div>{{ emptyTitle }}</div>
      <div>{{ emptyDescription }}</div>
    </div>
    <ul v-else class="invite-list__items invite-list__items--scrollable">
      <li v-for="item in items" :key="item.key" class="invite-list__item">
        <div class="invite-list__subject">
          <Avatar
            :initials="item.initials"
            :icon="item.initials ? '' : item.icon"
            :color="item.color"
            rounded
            size="large"
          />
          <div>
            <div class="invite-list__name">
              {{ item.name }}
              <Badge
                v-if="item.badge"
                :color="item.badgeColor"
                size="small"
                class="margin-left-1"
              >
                {{ item.badge }}
              </Badge>
            </div>
            <div v-if="item.subtitle" class="invite-list__subtitle">
              {{ item.subtitle }}
            </div>
          </div>
        </div>
        <div class="invite-list__access">
          <HelpIcon
            v-if="item.helpText"
            :tooltip="item.helpText"
            :tooltip-content-classes="[
              'tooltip__content--expandable',
              'tooltip__content--expandable-plain-text',
            ]"
          />
          <ScopeRoleSelector
            class="invite-list__role"
            :value="getRole(item)"
            :roles="item.roles || roles"
            :disabled="item.disabled"
            :allow-removing-role="item.allowRemovingRole !== false"
            :workspace="workspace"
            @delete="$emit('role-updated', item, null)"
            @input="({ uid }) => $emit('role-updated', item, uid)"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import ScopeRoleSelector from '@baserow/modules/core/components/invitation/ScopeRoleSelector'

/**
 * Direct access for existing users, teams and agents, plus pending invitations.
 * Callers provide normalized rows and own the permissions, API calls and
 * meaning of removal. Null roles emitted here request removal, not no access.
 */
export default {
  name: 'ScopeAccessList',
  components: { ScopeRoleSelector },
  props: {
    /**
     * Rows of `{ key, name, subtitle, badge, badgeColor, initials, icon, color,
     * roleUid, roles, disabled, allowRemovingRole, helpText }`, prepared by the
     * caller. `helpText`, when set, explains the role next to it.
     */
    items: {
      type: Array,
      required: true,
    },
    roles: {
      type: Array,
      required: true,
    },
    emptyTitle: {
      type: String,
      required: true,
    },
    emptyDescription: {
      type: String,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['role-updated'],
  methods: {
    getRole(item) {
      return (
        this.workspace._.roles.find((role) => role.uid === item.roleUid) || {
          uid: item.roleUid,
          name: item.roleUid,
        }
      )
    },
  },
}
</script>
