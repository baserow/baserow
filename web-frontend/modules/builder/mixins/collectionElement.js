import { mapActions, mapGetters } from 'vuex'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'
import _ from 'lodash'

export default {
  data() {
    return {
      adhocFilters: undefined,
      adhocSortings: undefined,
      adhocSearch: undefined,
      currentOffset: 0,
      errorNotified: false,
      resetTimeout: null,
      contentFetchEnabled: true,
    }
  },
  computed: {
    ...mapGetters({
      getLoading: 'elementContent/getLoading',
      getHasMorePage: 'elementContent/getHasMorePage',
      getElementContent: 'elementContent/getElementContent',
      getReset: 'elementContent/getReset',
      getPagesDataSourceById: 'dataSource/getPagesDataSourceById',
      getSharedPage: 'page/getSharedPage',
    }),
    reset() {
      return this.getReset(this.element)
    },
    sharedPage() {
      return this.getSharedPage(this.builder)
    },
    dataSource() {
      if (!this.element.data_source_id) {
        return null
      }
      const pages = [this.currentPage, this.sharedPage]
      return this.getPagesDataSourceById(pages, this.element.data_source_id)
    },
    dataSourceType() {
      if (!this.dataSource) {
        return null
      }
      return this.$registry.get('service', this.dataSource.type)
    },
    elementContent() {
      return this.getElementContent(this.element, this.applicationContext)
    },
    hasMorePage() {
      return this.getHasMorePage(this.element)
    },
    contentLoading() {
      return this.getLoading(this.element) && !this.elementIsInError
    },
    dispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        this.applicationContext
      )
    },
    elementHasSourceOfData() {
      return this.elementType.hasSourceOfData(this.element)
    },
    adhocRefinements() {
      return {
        filters: this.adhocFilters,
        sortings: this.adhocSortings,
        search: this.adhocSearch,
      }
    },
    elementIsInError() {
      return this.elementType.isInError({
        page: this.elementPage,
        element: this.element,
        builder: this.builder,
      })
    },
  },
  watch: {
    reset() {
      this.debouncedReset()
    },
    'element.schema_property'(newValue, oldValue) {
      if (newValue) {
        this.debouncedReset()
      }
    },
    'element.data_source_id'() {
      this.debouncedReset()
    },
    'element.items_per_page'() {
      this.debouncedReset()
    },
    dispatchContext: {
      handler(newValue, prevValue) {
        if (!_.isEqual(newValue, prevValue)) {
          this.debouncedReset()
        }
      },
      deep: true,
    },
    adhocRefinements: {
      handler(newValue, prevValue) {
        if (!_.isEqual(newValue, prevValue)) {
          this.debouncedReset()
        }
      },
    },
  },
  async fetch() {
    if (!this.elementIsInError && this.elementType.fetchAtLoad) {
      await this.fetchContent([0, this.element.items_per_page])
    }
  },
  methods: {
    ...mapActions({
      fetchElementContent: 'elementContent/fetchElementContent',
    }),
    debouncedReset() {
      clearTimeout(this.resetTimeout)
      this.resetTimeout = setTimeout(() => {
        this.contentFetchEnabled = true
        this.errorNotified = false
        this.currentOffset = 0
        this.loadMore(true)
      }, 500)
    },
    async fetchContent(range, replace) {
      if (!this.canFetch()) {
        return
      }
      try {
        await this.fetchElementContent({
          page: this.elementPage,
          element: this.element,
          dataSource: this.dataSource,
          data: this.dispatchContext,
          range,
          filters: this.adhocRefinements.filters,
          sortings: this.adhocRefinements.sortings,
          search: this.adhocRefinements.search,
          mode: this.applicationContext.mode,
          replace,
        })
        this.currentOffset += this.element.items_per_page
      } catch (error) {
        // Handle the HTTP error if needed
        this.onContentFetchError(error)

        // We need to only launch one toast error message per element,
        // not one per element fetch, or we can end up with many error
        // toasts per element sharing a datasource.
        if (!this.errorNotified) {
          this.errorNotified = true
          notifyIf(error)
        }
      }
    },
    async loadMore(replace = false) {
      await this.fetchContent(
        [this.currentOffset, this.element.items_per_page],
        replace
      )
    },
    /** Overrides this if you want to prevent data fetching */
    canFetch() {
      return this.contentFetchEnabled
    },

    /** Override this if you want to handle content fetch errors */
    onContentFetchError(error) {
      // If the request failed without reaching the server, `error.response`
      // will be `undefined`, so we need to check that before checking the
      // HTTP status code
      if (error.response && [400, 404].includes(error.response.status)) {
        this.contentFetchEnabled = false
      }
    },
  },
}
