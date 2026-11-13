<template>
  <ItemPickerCard
    :name="variation.name"
    :image="variation.createWidgetImage"
    :disabled="disabled"
    :unavailable="!isWidgetAvailable"
    :locked="!isWidgetAvailable"
    framed
    @click="widgetVariationSelected"
  >
    <component
      :is="deactivatedModal[0]"
      v-if="deactivatedModal != null"
      ref="deactivatedModal"
      v-bind="deactivatedModal[1]"
      :name="widgetType.name"
      :workspace="dashboard.workspace"
    ></component>
  </ItemPickerCard>
</template>

<script>
import ItemPickerCard from '@baserow/modules/core/components/ItemPickerCard'

export default {
  name: 'CreateWidgetCard',
  components: { ItemPickerCard },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widgetType: {
      type: Object,
      required: true,
    },
    variation: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['widget-variation-selected'],
  computed: {
    isWidgetAvailable() {
      return this.widgetType.isAvailable(this.dashboard.workspace.id)
    },
    deactivatedModal() {
      return this.widgetType.getDeactivatedModal()
    },
  },
  methods: {
    widgetVariationSelected() {
      if (this.disabled) {
        return
      }

      if (!this.isWidgetAvailable) {
        this.$refs.deactivatedModal.show()
        return
      }

      this.$emit('widget-variation-selected', this.variation)
    },
  },
}
</script>
