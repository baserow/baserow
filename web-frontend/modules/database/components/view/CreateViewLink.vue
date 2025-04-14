<template>
  <a
    ref="createViewLink"
    v-tooltip="tooltipText"
    class="select__footer-create-link"
    :class="{
      'select__footer-create-link--disabled':
        !viewType.isCompatibleWithDataSync(table.data_sync),
    }"
    :data-highlight="`create-view-${viewType.getType()}`"
    @click="select"
  >
    <i class="select__footer-create-icon" :class="viewType.iconClass"></i>
    {{ viewType.getName() }}
    <div v-if="deactivated" class="deactivated-label">
      <i class="iconoir-lock"></i>
    </div>
    <CreateViewModal
      ref="createModal"
      :table="table"
      :database="database"
      :view-type="viewType"
      @created="$emit('created', $event)"
    ></CreateViewModal>
    <component
      :is="deactivatedClickModal[0]"
      v-if="deactivatedClickModal !== null"
      ref="deactivatedClickModal"
      v-bind="deactivatedClickModal[1] || {}"
      :workspace="database.workspace"
    ></component>
    <i class="select__footer-create-link-icon iconoir-plus"></i>
  </a>
</template>

<script>
import CreateViewModal from '@baserow/modules/database/components/view/CreateViewModal'

export default {
  name: 'ViewsContext',
  components: {
    CreateViewModal,
  },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    viewType: {
      type: Object,
      required: true,
    },
  },
  computed: {
    tooltipText() {
      if (!this.viewType.isCompatibleWithDataSync(this.table.data_sync)) {
        return this.$t('createViewLink.inCompatibleWithDataSync')
      } else if (this.deactivated) {
        return this.deactivatedText
      }

      return null
    },
    deactivatedText() {
      return this.viewType.getDeactivatedText()
    },
    deactivated() {
      return this.viewType.isDeactivated(this.database.workspace.id)
    },
    deactivatedClickModal() {
      return this.viewType.getDeactivatedClickModal()
    },
  },
  methods: {
    select() {
      if (!this.viewType.isCompatibleWithDataSync(this.table.data_sync)) {
        // Don't do anything in case the view type not compatible with a data sync
        // table.
      } else if (!this.deactivated) {
        this.$refs.createModal.show(this.$refs.createViewLink)
      } else if (this.deactivated && this.deactivatedClickModal) {
        this.$refs.deactivatedClickModal.show()
      }
    },
  },
}
</script>
