<template>
  <li>
    <a
      v-tooltip="deactivated ? deactivatedText : null"
      class="choice-items__link"
      :class="{ active, disabled }"
      @click="select(exporterType)"
    >
      <i class="choice-items__icon" :class="exporterType.iconClass"></i>
      <span>{{ exporterType.getName() }}</span>
      <div v-if="deactivated" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
      <i
        v-if="active"
        class="choice-items__icon-active iconoir-check-circle"
      ></i>
    </a>
    <component
      :is="deactivatedClickModal[0]"
      v-if="deactivatedClickModal !== null"
      ref="deactivatedClickModal"
      v-bind="deactivatedClickModal[1]"
      :workspace="database.workspace"
      :name="exporterType.getName()"
    ></component>
  </li>
</template>

<script>
export default {
  name: 'ExporterTypeChoice',
  props: {
    database: {
      type: Object,
      required: true,
    },
    exporterType: {
      required: true,
      type: Object,
    },
    active: {
      required: true,
      type: Boolean,
    },
    disabled: {
      required: true,
      type: Boolean,
    },
  },
  computed: {
    deactivatedText() {
      return this.$registry
        .get('exporter', this.exporterType.type)
        .getDeactivatedText()
    },
    deactivated() {
      return this.$registry
        .get('exporter', this.exporterType.type)
        .isDeactivated(this.database.workspace.id)
    },
    deactivatedClickModal() {
      return this.$registry
        .get('exporter', this.exporterType.type)
        .getDeactivatedClickModal()
    },
  },
  methods: {
    select(exporterType) {
      if (this.deactivated && this.deactivatedClickModal) {
        this.$refs.deactivatedClickModal.show()
      } else if (!this.disabled && !this.deactivated) {
        this.$emit('selected', exporterType)
      }
    },
  },
}
</script>
