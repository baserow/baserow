<template>
  <div>
    <div class="select-row-modal__search">
      <i class="iconoir-search select-row-modal__search-icon"></i>
      <input
        ref="search"
        v-model="visibleSearch"
        type="text"
        :placeholder="$t('selectRowContent.search')"
        class="select-row-modal__search-input"
        @input="doSearch(visibleSearch, false)"
        @keydown.enter="doSearch(visibleSearch, true)"
        @keydown.up.down="$refs.search.blur()"
      />
    </div>
    <div
      class="select-row-modal__rows"
      :class="{
        'select-row-modal__rows--loading': loading || !metaDataLoaded,
      }"
    >
      <SimpleGrid
        v-if="metaDataLoaded && firstPageLoaded"
        :fixed-fields="[primary]"
        :fields="fields"
        :rows="rows"
        :full-height="true"
        :can-add-row="true"
        :with-footer="true"
        :show-hovered-row="true"
        :selected-rows="selectedRows"
        :multiple="multiple"
        :show-row-id="true"
        @add-row="$refs.rowCreateModal.show()"
        @row-click="select($event)"
      >
        <template #footLeft>
          <Paginator
            :total-pages="totalPages"
            :page="page"
            @change-page="fetch($event, true)"
          ></Paginator>
        </template>
      </SimpleGrid>
    </div>
    <RowCreateModal
      v-if="table"
      ref="rowCreateModal"
      :database="database"
      :table="table"
      :sortable="false"
      :all-fields-in-table="allFields"
      :visible-fields="allFields"
      :can-modify-fields="false"
      :presets="newRowPresets"
      @created="createRow"
    ></RowCreateModal>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'

import { notifyIf } from '@baserow/modules/core/utils/error'
import FieldService from '@baserow/modules/database/services/field'
import { populateField } from '@baserow/modules/database/store/field'
import RowService from '@baserow/modules/database/services/row'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import ViewService from '@baserow/modules/database/services/view'

import Paginator from '@baserow/modules/core/components/Paginator'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal'
import { prepareRowForRequest } from '@baserow/modules/database/utils/row'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import {
  filterVisibleFieldsFunction,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'
import { GridViewType } from '@baserow/modules/database/viewTypes'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid.vue'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'

export default {
  name: 'SelectRowContent',
  components: { Paginator, RowCreateModal, SimpleGrid },
  props: {
    tableId: {
      type: Number,
      required: true,
    },
    viewId: {
      type: [Number, null],
      required: false,
      default: null,
    },
    value: {
      type: Array,
      required: false,
      default: () => [],
    },
    initialSearch: {
      type: String,
      required: false,
      default: '',
    },
    multiple: {
      type: Boolean,
      required: false,
      default: false,
    },
    newRowPresets: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      // Indicates if we're loading new rows.
      loading: false,
      // Indicates if the metadata (fields, etc) has been loaded.
      metaDataLoaded: false,
      // Indicates if the page has loaded for the first time. We keep track of this
      // state to show a non flickering loading state for the user.
      firstPageLoaded: false,
      primary: null,
      fields: null,
      rows: [],
      search: '',
      visibleSearch: '',
      page: 1,
      totalPages: 0,
      lastHoveredRow: null,
      addRowHover: false,
      searchDebounce: null,
    }
  },
  computed: {
    allFields() {
      return [].concat(this.primary || [], this.fields || [])
    },
    databaseAndTable() {
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.tableId
        )

        if (foundTable) {
          return [application, foundTable]
        }
      }

      return [null, null]
    },
    database() {
      return this.databaseAndTable[0]
    },
    table() {
      return this.databaseAndTable[1]
    },
    selectedRows() {
      return this.value.map(({ id }) => id)
    },
  },
  async mounted() {
    // Focus the search field so the user may begin typing immediately.
    this.$nextTick(() => {
      this.focusSearch({})
    })

    // The first time we have to fetch the fields because they are unknown for this
    // table.
    if (!(await this.fetchFields(this.tableId))) {
      return false
    }

    await this.orderFieldsByFirstGridViewFieldOptions(this.tableId)

    // Because the page data depends on having some initial metadata we mark the state
    // as loaded after that. Only a loading animation is shown if there isn't any
    // data.
    this.metaDataLoaded = true

    this.doSearch(this.visibleSearch, false)

    this.$priorityBus.$on(
      'start-search',
      this.$priorityBus.level.HIGHEST,
      this.focusSearch
    )
  },
  beforeDestroy() {
    this.$priorityBus.$off('start-search', this.focusSearch)
  },
  methods: {
    /**
     * Fetches all the fields of the given table id. We need the fields so that we can
     * show the data in the correct format.
     */
    async fetchFields(tableId) {
      try {
        const { data } = await FieldService(this.$client).fetchAll(tableId)
        data.forEach((part, index, d) => {
          populateField(data[index], this.$registry)
        })
        const primaryIndex = data.findIndex((item) => item.primary === true)
        this.primary =
          primaryIndex !== -1 ? data.splice(primaryIndex, 1)[0] : null
        this.fields = data
        return true
      } catch (error) {
        notifyIf(error, 'row')
        this.$emit('hide')
        this.loading = false
        return false
      }
    },
    /**
     * This method fetches the first grid and the related field options. The ordering
     * of that grid view will be applied to the already fetched fields. If anything
     * goes wrong or if there isn't a grid view, the original order will be used.
     */
    async orderFieldsByFirstGridViewFieldOptions(tableId) {
      try {
        const { data: views } = await ViewService(this.$client).fetchAll(
          tableId,
          false,
          false,
          false,
          false,
          // We can safely limit to `1` because the backend provides the views ordered.
          1,
          // We want to fetch the first grid view because for that type we're sure it's
          // compatible with `filterVisibleFieldsFunction` and
          // `sortFieldsByOrderAndIdFunction`. Others might also work, but this
          // component is styled like a grid view and it makes to most sense to reflect
          // that here.
          GridViewType.getType()
        )

        if (views.length === 0) {
          return
        }

        const {
          data: { field_options: fieldOptions },
        } = await ViewService(this.$client).fetchFieldOptions(views[0].id)
        this.fields = this.fields
          .filter(filterVisibleFieldsFunction(fieldOptions))
          .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    /**
     * Does a row search in the table related to the state. It will also reset the
     * pagination.
     */
    doSearch(query, immediate) {
      const search = () => {
        this.search = query
        this.totalPages = 0
        return this.fetch(1, false)
      }
      if (this.searchDebounce) {
        this.searchDebounce.cancel()
      }
      this.loading = true
      if (immediate) {
        search()
      } else {
        this.searchDebounce = debounce(search, 400)
        this.searchDebounce()
      }
    },
    /**
     * Fetches the rows of a given page and adds them to the state. If a search query
     * has been stored in the state then that will be remembered.
     */
    async fetch(page, startLoading = true) {
      if (startLoading) {
        this.loading = true
      }

      try {
        const { data } = await RowService(this.$client).fetchAll({
          tableId: this.tableId,
          page,
          size: 10,
          search: this.search,
          searchMode: getDefaultSearchModeFromEnv(this.$config),
          viewId: this.viewId,
        })
        data.results.forEach((part, index) => populateRow(data.results[index]))

        this.page = page
        this.totalPages = Math.ceil(data.count / 10)
        this.rows = data.results
        this.loading = false
        this.firstPageLoaded = true
        return true
      } catch (error) {
        notifyIf(error, 'row')
        this.loading = false
        this.$emit('hide')
        return false
      }
    },
    /**
     * Called when the user selects a row.
     */
    select(row) {
      const exists = this.selectedRows.includes(row.id)

      // In multiple mode it's also possible to unselect.
      if (!this.multiple && exists) {
        return
      }

      this.$emit(exists ? 'unselected' : 'selected', {
        row,
        primary: this.primary,
        fields: this.fields,
      })
    },
    /**
     * Focuses the search field when the component mounts.
     */
    focusSearch({ event }) {
      event?.preventDefault()
      this.$refs.search?.focus()
    },
    async createRow({ row, callback }) {
      try {
        const preparedRow = prepareRowForRequest(
          row,
          this.allFields,
          this.$registry
        )

        const { data: rowCreated } = await RowService(this.$client).create(
          this.table.id,
          preparedRow
        )

        await this.fetch(this.page)

        // When you create a new row from a linked row that links to its own table,the
        // realtime update will be sent from you, and you won't receive it.Since you
        // don't receive the realtime update we have to manually add the new row to the
        // state. We can do that by using the same function that is used by the
        // realtime update. (`viewType.rowCreated`)
        const view = this.$store.getters['view/getSelected']
        const viewType = this.$registry.get('view', view.type)
        viewType.rowCreated(
          { store: this.$store },
          this.table.id,
          this.allFields,
          rowCreated,
          {},
          'page/'
        )

        this.select(populateRow(rowCreated))

        callback()
      } catch (error) {
        callback(error)
      }
    },
  },
}
</script>
