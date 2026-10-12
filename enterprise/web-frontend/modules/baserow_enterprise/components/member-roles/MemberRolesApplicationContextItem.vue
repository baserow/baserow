<template>
  <div>
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
    <InviteModal ref="inviteModal" :workspace="workspace" :target="target" />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="rbac"
      :workspace="application.workspace"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'MemberRolesApplicationContextItem',
  components: { PaidFeaturesModal, InviteModal },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    target() {
      return {
        type: 'scope',
        scopeType: 'application',
        scope: this.application,
      }
    },
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.RBAC,
        this.application.workspace.id
      )
    },
  },
}
</script>
