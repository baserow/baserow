<template>
  <span
    v-if="usedInDeps"
    v-tooltip:[tooltipOptions]="$t('dateDependency.dependencyFieldTooltip')"
    class="date-dependency__help-icon"
  >
    <a
      class="help-icon baserow-icon-dependancy"
      :class="{ 'color-error': hasError }"
      @click="openModal"
    >
    </a>
    <DateDependencyModal
      ref="modal"
      :workspace-id="workspace.id"
      :table="table"
    />
  </span>
</template>
<script>
import DateDependencyModal from '@baserow_enterprise/components/dateDependency/DateDependencyModal'

export default {
  components: { DateDependencyModal },

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

      tooltipOptions: {
        duration: 0.8,
        contentIsHtml: false,
      },
    }
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
      this.$refs.modal.show()
    },
  },
}
</script>
