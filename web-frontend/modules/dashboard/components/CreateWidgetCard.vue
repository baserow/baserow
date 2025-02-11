<template>
  <a
    class="create-widget-card"
    :class="{
      'create-widget-card--available': isWidgetAvailable,
    }"
    @click="widgetTypeSelected"
  >
    <div class="create-widget-card__img-container">
      <img :src="widgetType.createWidgetImage" />
    </div>
    <div class="create-widget-card__name">
      <span>{{ widgetType.name }}</span>
      <span v-if="!isWidgetAvailable">
        <i class="iconoir-lock create-widget-card__name-locked"></i>
      </span>
    </div>
    <component
      :is="deactivatedModal"
      v-if="deactivatedModal != null"
      ref="deactivatedModal"
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
    widgetTypeSelected() {
      if (!this.isWidgetAvailable) {
        this.$refs.deactivatedModal.show()
        return
      }

      this.$emit('widget-type-selected', this.widgetType.type)
    },
  },
}
</script>
