<template>
  <li class="context__menu-item">
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
    <MemberRolesModal
      ref="memberRolesModal"
      :database="database"
      :table="table"
      :view="view"
    />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="rbac"
      :workspace="database.workspace"
    ></PaidFeaturesModal>
  </li>
</template>

<script>
import MemberRolesModal from '@baserow_enterprise/components/member-roles/MemberRolesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'MemberRolesViewContextItem',
  components: { PaidFeaturesModal, MemberRolesModal },
  props: {
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.RBAC,
        this.database.workspace.id
      )
    },
  },
}
</script>
