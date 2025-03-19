<template>
  <div class="local-baserow-adhoc-header__container">
    <div class="local-baserow-adhoc-header">
      <div class="local-baserow-adhoc-header__item">
        <ViewFilter
          v-if="filterableFields.length"
          read-only
          :view="view"
          :fields="filterableFields"
          :disable-filter="false"
          @changed="handleFiltersChange"
        ></ViewFilter>
      </div>
      <div class="local-baserow-adhoc-header__item">
        <ViewSort
          v-if="sortableFields.length"
          read-only
          :view="view"
          :fields="sortableFields"
          @changed="handleSortingsChange"
        ></ViewSort>
      </div>
      <div class="flex-grow-1" />
      <div class="local-baserow-adhoc-header__item">
        <ViewSearch
          v-if="searchableFields.length"
          read-only
          always-hide-rows-not-matching-search
          :view="view"
          :fields="searchableFields"
          @refresh="handleSearchChange"
        ></ViewSearch>
      </div>
    </div>
  </div>
</template>

<script>
import ViewFilter from '@baserow/modules/database/components/view/ViewFilter'
import ViewSort from '@baserow/modules/database/components/view/ViewSort'
import ViewSearch from '@baserow/modules/database/components/view/ViewSearch'
import { getFilters, getOrderBy } from '@baserow/modules/database/utils/view'

export default {
  components: { ViewSearch, ViewSort, ViewFilter },
  props: {
    /**
     * An array of filterable, sortable and searchable *schema* properties.
     * To access the Baserow field response, these need to be reduced down
     * to just their `metadata`. This happens in the `computed` methods below.
     */
    filterableProperties: {
      type: Array,
      required: true,
    },
    sortableProperties: {
      type: Array,
      required: true,
    },
    searchableProperties: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      view: {
        filters: [],
        sortings: [],
        filter_groups: [],
        filter_type: 'AND',
        filters_disabled: false,
        _: { loading: false },
      },
    }
  },
  computed: {
    filterableFields() {
      return this.filterableProperties.map((prop) => prop.metadata)
    },
    sortableFields() {
      return this.sortableProperties.map((prop) => prop.metadata)
    },
    searchableFields() {
      return this.searchableProperties.map((prop) => prop.metadata)
    },
  },
  methods: {
    handleFiltersChange() {
      this.$emit('filters-changed', getFilters(this.view, true))
    },
    handleSortingsChange() {
      this.$emit('sortings-changed', getOrderBy(this.view, true))
    },
    handleSearchChange(value) {
      this.$emit('search-changed', value.activeSearchTerm)
    },
  },
}
</script>
