<template>
  <a
    class="create-widget-card"
    :class="{
      'create-widget-card--available': isWidgetAvailable,
    }"
    @click="widgetVariationSelected"
  >
    <div class="create-widget-card__img-container">
      <img :src="variation.createWidgetImage" />
    </div>
    <div class="create-widget-card__name">
      <span>{{ variation.name }}</span>
      <span v-if="!isWidgetAvailable">
        <i class="iconoir-lock create-widget-card__name-locked"></i>
      </span>
    </div>
    <component
      :is="deactivatedModal[0]"
      v-if="deactivatedModal != null"
      ref="deactivatedModal"
      v-bind="deactivatedModal[1]"
      :name="widgetType.name"
      :workspace="dashboard.workspace"
    ></component>
  </a>
</template>

<script>
export default {
  name: 'CreateWidgetCard',
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
  },
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
      if (!this.isWidgetAvailable) {
        this.$refs.deactivatedModal.show()
        return
      }

      this.$emit('widget-variation-selected', this.variation)
    },
  },
}
</script>
