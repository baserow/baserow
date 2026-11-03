<template>
  <ItemPickerModal
    ref="modal"
    :title="$t('createWidgetModal.title')"
    :search-placeholder="$t('createWidgetModal.searchPlaceholder')"
    :groups="widgetGroups"
  >
    <template #items="{ items }">
      <CreateWidgetCard
        v-for="widgetVariation in items"
        :key="widgetVariation.name"
        :dashboard="dashboard"
        :disabled="loading"
        :widget-type="widgetVariation.type"
        :variation="widgetVariation"
        @widget-variation-selected="widgetVariationSelected"
      />
    </template>
  </ItemPickerModal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import ItemPickerModal from '@baserow/modules/core/components/ItemPickerModal'
import CreateWidgetCard from '@baserow/modules/dashboard/components/CreateWidgetCard'

export default {
  name: 'CreateWidgetModal',
  components: { CreateWidgetCard, ItemPickerModal },
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
    widgetGroups() {
      return [
        {
          id: 'widgets',
          label: this.$t('createWidgetModal.widgets'),
          items: this.widgetVariations.filter(
            ({ type }) => !type.isFilterWidget
          ),
        },
        {
          id: 'filters',
          label: this.$t('createWidgetModal.filters'),
          items: this.widgetVariations.filter(
            ({ type }) => type.isFilterWidget
          ),
        },
      ]
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
