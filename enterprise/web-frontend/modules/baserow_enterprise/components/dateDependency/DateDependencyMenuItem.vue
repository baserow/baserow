<template>
  <div class="context__menu-item">
    <div>
      <a
        class="context__menu-item-link"
        @click="
          () => {
            if (deactivated) {
              $refs.paidFeaturesModal.show()
            } else {
              $refs.dateDependencyModal.show()
            }
          }
        "
      >
        <i class="context__menu-item-icon baserow-icon-dependancy"></i>
        {{ $t('dateDependencyModal.contextMenuItemLabel') }}
        <div v-if="deactivated" class="deactivated-label">
          <i class="iconoir-lock"></i>
        </div>
      </a>
    </div>
    <DateDependencyModal
      ref="dateDependencyModal"
      :table="tableObject"
      :workspace-id="database.workspace.id"
    >
    </DateDependencyModal>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="date_dependency"
      :workspace="database.workspace"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import DateDependencyModal from '@baserow_enterprise/components/dateDependency/DateDependencyModal.vue'

export default {
  name: 'DateDependencyTableContextItem',
  components: { DateDependencyModal, PaidFeaturesModal },
  props: {
    table: {
      type: Object,
      required: false,
      default: null,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.DATE_DEPENDENCY,
        this.database.workspace.id
      )
    },
    tableObject() {
      return this.table || this.view.table
    },
  },
}
</script>
