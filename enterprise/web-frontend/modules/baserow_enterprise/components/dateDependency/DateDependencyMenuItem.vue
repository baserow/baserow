<template>
  <div
    v-if="showEntry && featureFlagEnabled && (hasPermission || !featureEnabled)"
    class="context__menu-item"
  >
    <div>
      <a
        class="context__menu-item-link"
        @click="
          () => {
            if (featureEnabled) {
              $refs.dateDependencyModal.show()
            } else {
              $refs.paidFeaturesModal.show()
            }
            $emit('hide-context')
          }
        "
      >
        <i class="context__menu-item-icon baserow-icon-dependency"></i>
        {{ $t('dateDependencyModal.contextMenuItemLabel') }}
        <div v-if="deactivated" class="deactivated-label">
          <i class="iconoir-lock"></i>
        </div>
      </a>
    </div>
    <DateDependencyModal
      ref="dateDependencyModal"
      :table="table"
      :table-fields="fields"
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
import { FF_DATE_DEPENDENCY } from '@baserow/modules/core/plugins/featureFlags'

export default {
  name: 'DateDependencyMenuItem',
  components: { DateDependencyModal, PaidFeaturesModal },
  props: {
    table: {
      type: Object,
      required: false,
      default: null,
    },
    database: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: false,
      default: null,
    },
    fields: {
      type: [Array, null],
      required: false,
      default: null,
    },
  },
  computed: {
    featureEnabled() {
      return this.$hasFeature(
        EnterpriseFeatures.DATE_DEPENDENCY,
        this.database.workspace.id
      )
    },
    featureFlagEnabled() {
      return this.$featureFlagIsEnabled(FF_DATE_DEPENDENCY)
    },
    hasPermission() {
      return this.$hasPermission(
        'database.table.field_rules.set_field_rules',
        this.table,
        this.database.workspace.id
      )
    },
    showEntry() {
      if (!this.field) {
        return true
      }
      return (
        (this.field.type === 'date' && !this.field.date_include_time) ||
        (this.field.type === 'duration' &&
          this.field.duration_format === 'd h') ||
        (this.field.type === 'link_row' &&
          this.field.link_row_table_id === this.table.id)
      )
    },
  },
}
</script>
