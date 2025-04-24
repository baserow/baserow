<template>
  <div>
    <a
      class="context__menu-item-link"
      @click="
        () => {
          if (deactivated) {
            $refs.paidFeaturesModal.show()
          } else {
            $refs.memberRolesModal.show()
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
    <MemberRolesModal ref="memberRolesModal" :database="application" />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="rbac"
      :workspace="application.workspace"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import MemberRolesModal from '@baserow_enterprise/components/member-roles/MemberRolesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'MemberRolesDatabaseContextItem',
  components: { PaidFeaturesModal, MemberRolesModal },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.RBAC,
        this.application.workspace.id
      )
    },
  },
}
</script>
