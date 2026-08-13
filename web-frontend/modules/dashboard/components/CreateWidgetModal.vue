<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('createWidgetModal.title') }}
    </h2>
    <div class="create-widget-modal__cards">
      <CreateWidgetCard
        v-for="widgetVariation in widgetVariations"
        :key="widgetVariation.name"
        :dashboard="dashboard"
        :disabled="loading"
        :widget-type="widgetVariation.type"
        :variation="widgetVariation"
        @widget-variation-selected="widgetVariationSelected"
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
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['widget-variation-selected'],
  computed: {
    widgetTypes() {
      return this.$registry.getOrderedList('dashboardWidget')
    },
    widgetVariations() {
      return this.widgetTypes.reduce((acc, widgetType) => {
        return acc.concat(widgetType.variations)
      }, [])
    },
  },
  methods: {
    widgetVariationSelected(widgetVariation) {
      if (this.loading) {
        return
      }

      this.$emit('widget-variation-selected', widgetVariation)
      this.hide()
    },
  },
}
</script>
