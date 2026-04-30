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
      {{ $t('memberRolesWhiteboardContextItem.label') }}
      <div v-if="deactivated" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
    </a>
    <!--
      `MemberRolesModal` is named after the database use-case but its
      "database" prop is really treated as the application scope: the
      modal only reads `database.workspace.id` and uses `database` as
      the role-assignment scope, so passing the whiteboard application
      works the same way without modal changes. The other tabs (table,
      view) only render when their own props are provided.
    -->
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
  name: 'MemberRolesWhiteboardContextItem',
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
