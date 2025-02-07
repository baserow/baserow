<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('createWidgetModal.title') }}
    </h2>
    <div class="create-widget-modal__cards">
      <CreateWidgetCard
        v-for="widgetType in widgetTypes"
        :key="widgetType.type"
        :dashboard="dashboard"
        :widget-type="widgetType"
        @widget-type-selected="widgetTypeSelected"
      >
      </CreateWidgetCard>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import CreateWidgetCard from '@baserow/modules/dashboard/components/CreateWidgetCard'

export default {
  name: 'CreateWidgetModal',
  components: { CreateWidgetCard },
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
