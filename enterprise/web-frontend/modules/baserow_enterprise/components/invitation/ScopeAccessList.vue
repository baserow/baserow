<template>
  <div class="scope-access-list">
    <div v-if="items.length === 0" class="scope-access-list__empty">
      <div>{{ $t('shareScope.emptyTitle', { type: scopeTypeName }) }}</div>
      <div>{{ $t('shareScope.emptyDescription') }}</div>
    </div>
    <ul v-else class="scope-access-list__items">
      <li v-for="item in items" :key="item.key" class="scope-access-list__item">
        <div class="scope-access-list__subject">
          <Avatar
            :initials="item.initials"
            :icon="item.initials ? '' : item.icon"
            :color="item.color"
            rounded
            size="large"
          />
          <div>
            <div class="scope-access-list__name">
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
            <div v-if="item.subtitle" class="scope-access-list__subtitle">
              {{ item.subtitle }}
            </div>
          </div>
        </div>
        <RoleSelector
          :value="getRole(item)"
          :roles="roles"
          :disabled="item.disabled"
          :allow-removing-role="true"
          :workspace="workspace"
          @delete="$emit('role-updated', item, null)"
          @input="({ uid }) => $emit('role-updated', item, uid)"
        />
      </li>
    </ul>
  </div>
</template>

<script>
import RoleSelector from '@baserow_enterprise/components/member-roles/RoleSelector'

/**
 * Everyone with a role set directly on the object: members, teams, agents and
 * the pending email invitations, each with an editable and removable role.
 */
export default {
  name: 'ScopeAccessList',
  components: { RoleSelector },
  props: {
    /**
     * Rows of `{ key, name, subtitle, badge, badgeColor, initials, icon, color,
     * roleUid, disabled }`, prepared by the parent from the role assignments and
     * the scoped invitations.
     */
    items: {
      type: Array,
      required: true,
    },
    roles: {
      type: Array,
      required: true,
    },
    scopeTypeName: {
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
