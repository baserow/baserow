<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('createWidgetModal.title') }}
    </h2>
    <div>
      <a
        v-for="widgetType in widgetTypes"
        :key="widgetType.type"
        class="create-widget-card"
        @click="widgetTypeSelected(widgetType.type)"
      >
        <div class="create-widget-card__img-container">
          <img :src="widgetType.createWidgetImage" />
        </div>
        <div class="create-widget-card__name">
          {{ widgetType.name }}
        </div>
      </a>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'CreateWidgetModal',
  mixins: [modal],
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  computed: {
    widgetTypes() {
      return this.$registry.getAll('dashboardWidget')
    },
  },
  methods: {
    widgetTypeSelected(widgetType) {
      this.$emit('widget-type-selected', widgetType)
      this.hide()
    },
  },
}
</script>
