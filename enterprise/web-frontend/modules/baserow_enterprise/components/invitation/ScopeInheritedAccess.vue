<template>
  <div class="scope-access-list__item">
    <div class="scope-access-list__subject">
      <Avatar
        :initials="nameAbbreviation(workspace.name)"
        rounded
        size="large"
      />
      <div>
        <div class="scope-access-list__name">
          {{ $t('shareScope.everyoneAt', { name: workspace.name }) }}
        </div>
        <div class="scope-access-list__subtitle">
          <template v-for="(entry, index) in roleCounts" :key="entry.uid">
            <span v-if="index > 0"> • </span>
            {{ $t('shareScope.roleCount', entry) }}
          </template>
        </div>
      </div>
    </div>
    <div>
      <a ref="fromLink" @click="$refs.context.toggle($refs.fromLink)">
        {{ $t('shareScope.fromWorkspace') }}
        <i class="iconoir-nav-arrow-down"></i>
      </a>
      <Context ref="context" class="scope-access-list__context">
        <p>
          {{
            $t('shareScope.fromWorkspaceExplanation', { type: scopeTypeName })
          }}
        </p>
        <nuxt-link
          :to="{
            name: 'settings-members',
            params: { workspaceId: workspace.id },
          }"
        >
          {{ $t('shareScope.manageWorkspaceRoles') }}
        </nuxt-link>
      </Context>
    </div>
  </div>
</template>

<script>
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

const ROLES_WITHOUT_ACCESS = ['NO_ACCESS', 'NO_ROLE_LOW_PRIORITY']

/**
 * The people who reach the object through their workspace role, summarised per
 * role. Roles on a parent database are not summarised yet.
 */
export default {
  name: 'ScopeInheritedAccess',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    scopeTypeName: {
      type: String,
      required: true,
    },
  },
  computed: {
    roleCounts() {
      const counts = {}
      for (const user of this.workspace.users || []) {
        counts[user.permissions] = (counts[user.permissions] || 0) + 1
      }
      return this.workspace._.roles
        .filter(
          (role) => counts[role.uid] && !ROLES_WITHOUT_ACCESS.includes(role.uid)
        )
        .map((role) => ({
          uid: role.uid,
          role: role.name,
          count: counts[role.uid],
        }))
    },
  },
  methods: {
    nameAbbreviation,
  },
}
</script>
