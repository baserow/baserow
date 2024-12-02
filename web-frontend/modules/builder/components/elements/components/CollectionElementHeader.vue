<template>
  <component
    :is="serviceType.adhocHeaderComponent"
    v-if="dataSource"
    class="collection-element__header margin-bottom-1"
    :sortable-properties="
      elementType.adhocSortableProperties(element, dataSource)
    "
    :filterable-properties="
      elementType.adhocFilterableProperties(element, dataSource)
    "
    :searchable-properties="
      elementType.adhocSearchableProperties(element, dataSource)
    "
    @filters-changed="$emit('filters-changed', $event)"
    @sortings-changed="$emit('sortings-changed', $event)"
    @search-changed="$emit('search-changed', $event)"
  />
</template>

<script>
export default {
  inject: ['builder', 'currentPage'],
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    dataSource() {
      return this.$store.getters['dataSource/getPagesDataSourceById'](
        [this.currentPage, this.sharedPage],
        this.element.data_source_id
      )
    },
    elementType() {
      return this.$registry.get('element', this.element.type)
    },
    serviceType() {
      return this.$registry.get('service', this.dataSource?.type)
    },
  },
}
</script>
