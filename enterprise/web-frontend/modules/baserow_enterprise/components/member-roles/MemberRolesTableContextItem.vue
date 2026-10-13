<template>
  <div>
    <div class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="
          () => {
            if (deactivated) {
              $refs.paidFeaturesModal.show()
            } else {
              $refs.inviteModal.show()
            }
          }
        "
      >
        <i class="context__menu-item-icon iconoir-community"></i>
        {{ $t('memberRolesDatabaseContexItem.label') }}
        <div v-if="deactivated" class="deactivated-label">
          <i class="iconoir-lock"></i>
        </div>
      </a>
    </div>
    <InviteModal ref="inviteModal" :workspace="workspace" :target="target" />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="rbac"
      :workspace="database.workspace"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'MemberRolesTableContextItem',
  components: { PaidFeaturesModal, InviteModal },
  props: {
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    target() {
      return {
        type: 'scope',
        scopeType: 'database_table',
        scope: this.table,
        database: this.database,
      }
    },
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.RBAC,
        this.database.workspace.id
      )
    },
  },
}
</script>
