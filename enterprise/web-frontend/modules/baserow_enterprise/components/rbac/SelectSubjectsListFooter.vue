<template>
  <div
    class="select-list-footer"
    :class="{ 'select-list-footer--single': !showRoleSelector }"
  >
    <div v-if="showRoleSelector" class="select-list-footer__left-side">
      <RoleSelector
        v-model="roleSelected"
        :roles="roles"
        :workspace="workspace"
      />
    </div>
    <div>
      <HelpIcon
        :tooltip="$t('selectSubjectsListFooter.helpTooltip')"
        class="margin-right-1"
      ></HelpIcon>
      <Button
        type="primary"
        :disabled="!inviteEnabled"
        @click="inviteEnabled ? $emit('invite', roleSelected) : null"
        >{{
          $t('selectSubjectsListFooter.invite', {
            count,
            type: subjectTypeLabel,
          })
        }}
      </Button>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import RoleSelector from '@baserow_enterprise/components/member-roles/RoleSelector'
import { filterRoles } from '@baserow_enterprise/utils/roles'

export default {
  name: 'SelectSubjectsListFooter',
  emits: ['invite'],
  components: { RoleSelector },
  props: {
    showRoleSelector: {
      type: Boolean,
      default: false,
    },
    count: {
      type: Number,
      required: true,
    },
    subjectType: {
      type: String,
      required: true,
    },
    scopeType: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      roleSelected: {},
    }
  },
  computed: {
    ...mapGetters({ workspace: 'workspace/getSelected' }),
    subjectTypeLabel() {
      switch (this.subjectType) {
        case 'auth.User':
          return this.$t('selectSubjectsListFooter.types.members')
        case 'baserow_enterprise.Team':
          return this.$t('selectSubjectsListFooter.types.teams')
        default:
          return ''
      }
    },
    roles() {
      return this.workspace
        ? filterRoles(this.workspace._.roles, {
            scopeType: this.scopeType,
            subjectType: this.subjectType,
          })
        : []
    },
    inviteEnabled() {
      return this.count !== 0
    },
  },
  mounted() {
    // Set a default selected role, the last role is usually the one with the least
    // access
    this.roleSelected =
      this.roles.length > 0 ? this.roles[this.roles.length - 1] : {}
  },
}
</script>
