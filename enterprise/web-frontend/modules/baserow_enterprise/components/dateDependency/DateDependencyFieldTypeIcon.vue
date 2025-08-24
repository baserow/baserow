<template>
  <span
    v-if="usedInDeps"
    v-tooltip="tooltipText"
    class="date-dependency__help-icon"
  >
    <a
      class="help-icon baserow-icon-dependency"
      :class="{ 'color-error': hasError }"
      @click="openModal"
    >
    </a>
    <DateDependencyModal
      ref="modal"
      :workspace-id="workspace.id"
      :table="table"
    />

    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="date_dependency"
      :workspace="workspace"
    ></PaidFeaturesModal>
  </span>
</template>
<script>
import DateDependencyModal from '@baserow_enterprise/components/dateDependency/DateDependencyModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  components: { DateDependencyModal, PaidFeaturesModal },

  props: {
    table: { type: Object, required: true },
    workspace: { type: Object, required: true },
    field: { type: Object, required: true },
  },
  data() {
    return {
      usedInDeps: false,
      deps: [],
      hasError: false,
      errorText: null,
      tooltipOptions: {
        duration: 0.8,
        contentIsHtml: false,
      },
    }
  },
  computed: {
    deactivated() {
      return !this.$hasFeature(
        EnterpriseFeatures.DATE_DEPENDENCY,
        this.workspace.id
      )
    },
    tooltipText() {
      if (this.hasError) {
        return (
          this.errorText ||
          this.$t('dateDependencyModal.dependencyFieldTooltipError')
        )
      } else {
        return this.$t('dateDependencyModal.dependencyFieldTooltip')
      }
    },
  },
  watch: {
    deps: function () {
      this.calculateState()
    },
  },
  mounted() {
    this.getUsedInDeps()
    this.$bus.$on('fieldRules/updated', this.handleBusMessage)
  },
  methods: {
    reset() {
      this.usedInDeps = false
      this.deps = []
      this.hasError = false
      this.errorText = ''
    },
    calculateState() {
      const fieldId = this.field.id
      this.deps.forEach((dep) => {
        if (
          dep.is_active &&
          (fieldId === dep.start_date_field_id ||
            fieldId === dep.end_date_field_id ||
            fieldId === dep.duration_field_id ||
            fieldId === dep.dependency_linkrow_field_id)
        ) {
          this.usedInDeps = true
        }
        if (!dep.is_valid && dep.is_active) {
          this.hasError = true
          this.errorText = dep.error_text
        }
      })
    },
    handleBusMessage(rule) {
      if (rule.table_id === this.table.id) {
        this.getUsedInDeps()
      }
    },
    getUsedInDeps() {
      this.reset()
      this.deps = this.$store.getters['fieldRules/getRulesByType']({
        tableId: this.table.id,
        ruleType: 'date_dependency',
      })
      this.calculateState()
    },
    openModal() {
      if (this.deactivated) {
        this.$refs.paidFeaturesModal.show()
      } else {
        this.$refs.modal.show()
      }
    },
  },
}
</script>
