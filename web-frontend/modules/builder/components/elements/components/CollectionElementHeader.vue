<template>
  <component
    :is="serviceType.adhocHeaderComponent"
    v-if="dataSource && hasRefinements"
    class="collection-element__header margin-bottom-1"
    :sortable-properties="sortableProperties"
    :filterable-properties="filterableProperties"
    :searchable-properties="searchableProperties"
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
  emits: ['filters-changed', 'search-changed', 'sortings-changed'],
  computed: {
    hasRefinements() {
      return (
        this.sortableProperties.length ||
        this.filterableProperties.length ||
        this.searchableProperties.length
      )
    },
    sortableProperties() {
      return this.dataSource
        ? this.elementType.adhocSortableProperties(
            this.element,
            this.dataSource
          )
        : []
    },
    filterableProperties() {
      return this.dataSource
        ? this.elementType.adhocFilterableProperties(
            this.element,
            this.dataSource
          )
        : []
    },
    searchableProperties() {
      return this.dataSource
        ? this.elementType.adhocSearchableProperties(
            this.element,
            this.dataSource
          )
        : []
    },
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
