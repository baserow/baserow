<template>
  <div class="data-table">
    <header class="data-table__header">
      <h1 class="data-table__title">
        <slot name="title" :count="totalCount" :loading="initialLoading"></slot>
      </h1>
      <div class="data-table__actions">
        <CrudTableSearch
          v-if="enableSearch"
          ref="crudTableSearch"
          :loading="loading && loaded"
          :initial-search-term="defaultSearch || ''"
          @search-changed="doSearch"
        />
        <slot name="header-right-side"></slot>
        <slot name="primary-action"></slot>
      </div>
    </header>
    <slot name="header-filters"></slot>
    <div
      class="data-table__body"
      :class="{ 'data-table__body--empty': showEmptyState }"
    >
      <table class="data-table__table" :aria-busy="loading">
        <thead v-if="!showEmptyState">
          <tr v-if="loading" class="data-table__table-row" aria-hidden="true">
            <th
              class="data-table__table-cell data-table__table-cell--header"
              :colspan="columns.length"
            >
              <div class="data-table__table-cell-head skeleton">
                <SkeletonBlock width="200px"></SkeletonBlock>
              </div>
            </th>
          </tr>
          <tr v-else class="data-table__table-row">
            <th
              v-for="col in columns"
              :key="'head-' + col.key"
              :style="col.widthPerc ? `--width: ${col.widthPerc}%` : ''"
              class="data-table__table-cell data-table__table-cell--header"
              :class="{
                'data-table__table-cell--sticky-left': col.stickyLeft,
                'data-table__table-cell--sticky-right': col.stickyRight,
              }"
            >
              <div class="data-table__table-cell-head">
                <template v-if="col.sortable">
                  <div>
                    <button
                      type="button"
                      class="data-table__table-cell-head-link"
                      @click="toggleSort(col)"
                    >
                      {{ col.header }}
                    </button>
                    <HelpIcon v-if="col.helpText" :tooltip="col.helpText" />
                  </div>
                  <div class="data-table__table-cell-head-sort-icon">
                    <template v-if="sorted(col)">
                      <i :class="sortIcon(col)"></i>
                      {{ sortIndex(col) }}
                    </template>
                  </div>
                </template>
                <template v-else>
                  <div>
                    {{ col.header }}
                    <HelpIcon
                      v-if="col.helpText"
                      :tooltip="col.helpText"
                    /></div
                ></template>
              </div>
            </th>
          </tr>
        </thead>
        <tbody v-if="loading">
          <CrudTableSkeletonRows :columns="columns" :count="skeletonRowCount" />
        </tbody>
        <tbody v-else-if="showEmptyState">
          <tr>
            <td :colspan="columns.length || 1" class="data-table__empty-cell">
              <div class="data-table__empty">
                <slot v-if="!hasActiveFilters" name="empty">
                  <p>{{ $t('crudTable.empty') }}</p>
                </slot>
                <p v-else>{{ $t('crudTable.noResults') }}</p>
                <div
                  v-if="!hasActiveFilters && $slots['primary-action']"
                  class="data-table__empty-action"
                >
                  <slot name="primary-action"></slot>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
        <tbody v-else-if="$slots.rows">
          <slot
            name="rows"
            :rows="rows"
            :columns="columns"
            :update-row="updateRow"
            :delete-row="deleteRow"
            :refresh="refresh"
          />
        </tbody>
        <template v-else>
          <CrudTableRow
            v-for="row in rows"
            :key="row[rowIdKey]"
            :row="row"
            :columns="columns"
            :expandable="canExpandRow(row)"
            :expanded="canExpandRow(row) && expandedRows.has(row[rowIdKey])"
            :expand-column-key="expandColumnKey"
            v-bind="$attrs"
            @toggle="toggleRow(row)"
            @row-context="$emit('row-context', $event)"
            @row-update="updateRow"
            @row-delete="deleteRow"
            @refresh="refresh"
          >
            <template #expanded-row="slotProps">
              <slot
                name="expanded-row"
                v-bind="slotProps"
                :update-row="updateRow"
                :delete-row="deleteRow"
                :refresh="refresh"
              />
            </template>
            <template #row-expansion-toggle="slotProps">
              <slot name="row-expansion-toggle" v-bind="slotProps" />
            </template>
          </CrudTableRow>
        </template>
      </table>
    </div>
    <div
      v-if="service.options.isPaginated && (!showEmptyState || page > 1)"
      class="data-table__footer"
    >
      <Paginator
        v-skeleton="{ loading: initialLoading, height: '20px' }"
        :page="page"
        :total-pages="totalPages"
        @change-page="fetch"
      ></Paginator>
    </div>
    <slot
      name="menus"
      :update-row="updateRow"
      :delete-row="deleteRow"
      :refresh="refresh"
    ></slot>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import CrudTableRow from '@baserow/modules/core/components/crudTable/CrudTableRow'
import CrudTableSearch from '@baserow/modules/core/components/crudTable/CrudTableSearch'
import CrudTableSkeletonRows from '@baserow/modules/core/components/crudTable/CrudTableSkeletonRows'
import Paginator from '@baserow/modules/core/components/Paginator'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import _ from 'lodash'
import isObject from 'lodash/isObject'

/**
 * This component is a generic wrapper for a basic crud service which displays its
 * data in a table format. Comes with basic features like column sorting, searching
 * by a field etc.
 *
 * Any listeners placed on the CrudTable will be passed through and placed on every
 * instance of the provided columns cellComponent. This allows components using
 * CrudTable to easily communicate with their specific cellComponents.
 *
 * Slots:
 *  #title: Header title, with the result count and initial loading state.
 *  #header-right-side: Additional controls beside the search.
 *  #primary-action: Main action, also shown in the unfiltered empty state.
 *  #empty: Empty state when no search or filters are active.
 *  #menus: Placed in the footer and expected to only contain Contexts and Modals.
 *          Receives updateRow, deleteRow and refresh to synchronize table data.
 *  #rows: Can optionally replace the rows in the table (including expansion).
 *  #expanded-row: One or more <tr> elements, with row, columns, updateRow,
 *                 deleteRow and refresh slot props. Use <td :colspan="columns.length">
 *                 for full-width content, or cells aligned to the existing columns.
 *  #row-expansion-toggle: Optional content beside the disclosure chevron.
 *                         Receives row and expanded; CrudTable owns the button.
 */
export default {
  name: 'CrudTable',
  components: {
    Paginator,
    CrudTableSearch,
    CrudTableSkeletonRows,
    CrudTableRow,
  },
  inheritAttrs: false,
  props: {
    /** With an expanded-row slot, optionally restrict expansion to eligible rows. */
    rowExpandable: {
      type: Function,
      default: null,
    },
    /** Column containing the disclosure control; defaults to the first column. */
    expandColumnKey: {
      type: String,
      default: null,
    },
    /**
     * A service which provides a fetch(pageNumber, searchParam, columnSortsList)
     * method which returns an object in the form of:
     * ```
     * {
     *   count: 1, // the number of total results available (including other pages)
     *   results: [ // A row object with an attribute matching the provided column keys
     *     {
     *       column1Key: value,
     *       column2Key: value
     *     }
     *   ]
     * }
     * ```
     * CrudTable will call this method with the current page and assume the returned
     * results have a max page size of 100 to calculate the total number of pages.
     *
     * Each service can also define an `options` attribute in which it can set
     * `isPaginated` to `false`. If that attribute is set, the CrudTable will just
     * fetch the provided endpoint without any pagination.
     *
     * If the user has provided a search query this will be passed in the second
     * argument.
     *
     * Finally if the user has sorted sortable columns they will be passed in the third
     * argument as an ordered array of objects in the form of:
     * ```
     * {
     *   key: 'column1Key',
     *   direction: 'asc' or 'desc',
     * }
     * ```
     */
    service: {
      required: true,
      type: Object,
    },
    /**
     * An ordered array of columns to show. The column keys must be present in every
     * row returned by the service.
     */
    columns: {
      required: false,
      type: Array,
      default: () => [],
      validator: (prop) => prop.every((e) => e instanceof CrudTableColumn),
    },
    /**
     * The row attribute to be used as the key for the row. Must be present on every row
     * returned from the service.
     * The delete-row cellComponent event / deleteRow slot prop expects that the
     * emitted/passed object is the rowIdKey value for the row to be deleted.
     * The edit-row cellComponent event / editRow slotProp expects the row object
     * emitted/passed contains this key.
     */
    rowIdKey: {
      required: true,
      type: String,
    },
    defaultColumnSorts: {
      required: false,
      type: Array,
      default: () => [],
      validator: (prop) => _.isArray(prop),
    },
    filters: {
      required: false,
      type: Object,
      default: () => ({}),
      validator: (prop) => isObject(prop),
    },
    enableSearch: {
      required: false,
      type: Boolean,
      default: true,
    },
    /**
     * Optionally makes the table start with the provided search query already applied,
     * for example based on a route query parameter.
     */
    defaultSearch: {
      required: false,
      type: String,
      default: null,
    },
  },
  emits: ['row-context', 'rows-update', 'total-count-update', 'row-toggle'],
  data() {
    return {
      loading: true,
      loaded: false,
      page: 1,
      totalPages: 0,
      totalCount: 0,
      lastFetchId: 0,
      searchQuery: this.defaultSearch || false,
      rows: [],
      expandedRows: new Set(),
      columnSorts: this.defaultColumnSorts,
    }
  },
  computed: {
    hasActiveFilters() {
      return !!this.searchQuery || Object.keys(this.filters).length > 0
    },
    initialLoading() {
      return this.loading && !this.loaded
    },
    /**
     * Matches the number of rows that are already there, so that refetching
     * doesn't change the height of the table.
     */
    skeletonRowCount() {
      return this.rows.length || 10
    },
    showEmptyState() {
      return !this.loading && this.rows.length === 0
    },
  },
  watch: {
    rows() {
      this.$emit('rows-update', this.rows)
    },
    filters() {
      this.expandedRows.clear()
      this.fetch()
    },
  },
  async mounted() {
    await this.fetch()
  },
  methods: {
    canExpandRow(row) {
      return (
        !!this.$slots['expanded-row'] &&
        (!this.rowExpandable || this.rowExpandable(row))
      )
    },
    toggleRow(row) {
      if (!this.canExpandRow(row)) return
      const key = row[this.rowIdKey]
      const expanded = !this.expandedRows.has(key)
      if (expanded) {
        this.expandedRows.add(key)
      } else {
        this.expandedRows.delete(key)
      }
      this.$emit('row-toggle', { row, expanded })
    },
    /**
     * If the column is sortable cycles through applying descending, then ascending and
     * then no sort to this column.
     */
    toggleSort(column) {
      if (!column.sortable) {
        return
      }
      const i = this.sortIndex(column)
      if (i === -1) {
        this.columnSorts.push({ key: column.key, direction: 'desc' })
      } else {
        const current = this.columnSorts[i]
        if (current.direction === 'desc') {
          this.columnSorts.splice(i, 1, {
            key: current.key,
            direction: 'asc',
          })
        } else {
          this.columnSorts.splice(i, 1)
        }
      }
      this.fetch(1)
    },
    sortIcon(column) {
      const i = this.sortIndex(column)
      return this.columnSorts[i].direction === 'desc'
        ? 'iconoir-sort-up'
        : 'iconoir-sort-down'
    },
    sorted(column) {
      return this.sortIndex(column) !== -1
    },
    sortIndex(column) {
      return this.columnSorts.findIndex((c) => c.key === column.key)
    },
    async doSearch(searchQuery) {
      this.expandedRows.clear()
      this.totalPages = 0
      this.searchQuery = searchQuery
      await this.fetch(1)
    },
    setSearch(searchQuery) {
      if (this.$refs.crudTableSearch) {
        this.$refs.crudTableSearch.setSearchTerm(searchQuery)
      } else {
        this.doSearch(searchQuery)
      }
    },
    /**
     * Fetches the rows of a given page and adds them to the state.
     */
    async fetch(page = null) {
      if (page == null && this.service.options.isPaginated) {
        page = 1
      }

      if (page !== null && page !== this.page) {
        this.expandedRows.clear()
      }

      // A newer request can resolve before an older one, so the response of an
      // older request must never overwrite the state of a newer one.
      const fetchId = ++this.lastFetchId
      this.loading = true
      try {
        const { data } = await this.service.fetch(
          this.service.options.baseUrl,
          page,
          this.searchQuery,
          this.columnSorts,
          this.filters,
          this.service.options
        )

        if (fetchId !== this.lastFetchId) {
          return
        }

        if (this.service.options.isPaginated) {
          this.page = page
          this.totalPages = Math.max(Math.ceil(data.count / 100), 1)
          this.$emit('total-count-update', data.count)
        }

        this.rows = _.isArray(data) ? data : data.results
        this.totalCount = data.count ?? this.rows.length
        const visibleKeys = new Set(
          this.rows.filter(this.canExpandRow).map((row) => row[this.rowIdKey])
        )
        this.expandedRows = new Set(
          [...this.expandedRows].filter((key) => visibleKeys.has(key))
        )
      } catch (error) {
        if (fetchId !== this.lastFetchId) {
          return
        }
        notifyIf(error, 'row')
      }

      this.loading = false
      this.loaded = true
    },
    updateRow(updatedRow) {
      const i = this.rows.findIndex(
        (u) => u[this.rowIdKey] === updatedRow[this.rowIdKey]
      )
      Object.assign(this.rows[i], updatedRow)
    },
    upsertRow(row) {
      const i = this.rows.findIndex(
        (u) => u[this.rowIdKey] === row[this.rowIdKey]
      )
      if (i >= 0) {
        Object.assign(this.rows[i], row)
      } else {
        this.rows.unshift(row)
        this.totalCount += 1
      }
    },
    deleteRow(rowId) {
      this.expandedRows.delete(rowId)
      const i = this.rows.findIndex((u) => u[this.rowIdKey] === rowId)
      if (i !== -1) {
        this.rows.splice(i, 1)
        this.totalCount = Math.max(0, this.totalCount - 1)
      }
    },
    refresh() {
      return this.fetch(this.page)
    },
  },
}
</script>
