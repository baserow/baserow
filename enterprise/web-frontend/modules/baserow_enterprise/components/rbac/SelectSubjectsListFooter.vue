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
        @click="handleInviteClick"
        >{{
          $t('selectSubjectsListFooter.invite', {
            count,
            type: subjectTypeLabel,
          })
        }}
      </Button>
    </div>
    <NoAccessConfirmModal
      ref="noAccessConfirmModal"
      @confirm="emitInvite"
    ></NoAccessConfirmModal>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import RoleSelector from '@baserow_enterprise/components/member-roles/RoleSelector'
import NoAccessConfirmModal from '@baserow_enterprise/components/rbac/NoAccessConfirmModal'
import { filterRoles } from '@baserow_enterprise/utils/roles'

export default {
  name: 'SelectSubjectsListFooter',
  components: { RoleSelector, NoAccessConfirmModal },
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
    // Set a default selected role, preferring VIEWER as a safe default that still
    // allows access instead of NO_ACCESS which could accidentally lock users out
    this.roleSelected = this.getDefaultRole()
  },
  methods: {
    getDefaultRole() {
      if (this.roles.length === 0) return {}
      // Prefer VIEWER role as safe default, fall back to last role
      const viewerRole = this.roles.find((role) => role.uid === 'VIEWER')
      return viewerRole || this.roles[this.roles.length - 1]
    },
    handleInviteClick() {
      if (!this.inviteEnabled) return
      // Show confirmation modal when NO_ACCESS role is selected
      if (this.roleSelected?.uid === 'NO_ACCESS') {
        this.$refs.noAccessConfirmModal.show()
      } else {
        this.emitInvite()
      }
    },
    emitInvite() {
      this.$emit('invite', this.roleSelected)
    },
  },
}
</script>
