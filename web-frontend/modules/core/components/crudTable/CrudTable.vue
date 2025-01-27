<template>
  <div class="data-table" :class="{ 'data-table--loading': loading }">
    <header class="data-table__header">
      <h1 class="data-table__title">
        <slot name="title"></slot>
      </h1>
      <div class="data-table__actions">
        <CrudTableSearch
          v-if="enableSearch"
          :loading="loading"
          @search-changed="doSearch"
        />
        <slot name="header-right-side"></slot>
      </div>
    </header>
    <slot name="header-filters"></slot>
    <div class="data-table__body">
      <table class="data-table__table">
        <thead>
          <tr class="data-table__table-row">
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
                    <a
                      class="data-table__table-cell-head-link"
                      @click="toggleSort(col)"
                      >{{ col.header }}</a
                    >
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
        <tbody>
          <tr
            v-for="row in rows"
            :key="'row-' + row.id"
            class="data-table__table-row"
          >
            <td
              v-for="col in columns"
              :key="'col-' + col.key"
              class="data-table__table-cell"
              :class="{
                'data-table__table-cell--sticky-left': col.stickyLeft,
                'data-table__table-cell--sticky-right': col.stickyRight,
                [`data-table__table-cell--${col.key}`]: true,
              }"
              @contextmenu="$emit('row-context', { col, row, event: $event })"
            >
              <div class="data-table__table-cell-content">
                <component
                  :is="col.cellComponent"
                  :row="row"
                  :column="col"
                  v-on="$listeners"
                  @row-update="updateRow"
                  @row-delete="deleteRow"
                  @refresh="refresh"
                />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="service.options.isPaginated" class="data-table__footer">
      <Paginator
        :page="page"
        :total-pages="totalPages"
        @change-page="fetch"
      ></Paginator>
    </div>
    <slot name="menus" :update-row="updateRow" :delete-row="deleteRow"></slot>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import CrudTableSearch from '@baserow/modules/core/components/crudTable/CrudTableSearch'
import Paginator from '@baserow/modules/core/components/Paginator'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import { isArray } from 'lodash'
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
 * Provides two slots:
 *  #header: Placed within the header of the CrudTable.
 *  #menus: Placed in the footer and expected to only contain Contexts and Modals.
 *          Two slot props are provided `updateRow` and `deleteRow` which are functions
 *          called when your menu has changed the row state which trigger the CrudTable
 *          to rerender the rows with the new data.
 */
export default {
  name: 'CrudTable',
  components: { Paginator, CrudTableSearch },
  props: {
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
      validator: (prop) => isArray(prop),
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
  },
  data() {
    return {
      loading: false,
      page: 1,
      totalPages: 0,
      searchQuery: false,
      rows: [],
      columnSorts: this.defaultColumnSorts,
    }
  },
  async fetch() {
    await this.fetch()
  },
  watch: {
    rows() {
      this.$emit('rows-update', this.rows)
    },
    filters() {
      this.fetch()
    },
  },
  methods: {
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
      this.totalPages = 0
      this.searchQuery = searchQuery
      await this.fetch(1)
    },
    /**
     * Fetches the rows of a given page and adds them to the state.
     */
    async fetch(page = null) {
      if (page == null && this.service.options.isPaginated) {
        page = 1
      }

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

        if (this.service.options.isPaginated) {
          this.page = page
          this.totalPages = Math.max(Math.ceil(data.count / 100), 1)
        }

        this.rows = isArray(data) ? data : data.results
      } catch (error) {
        notifyIf(error, 'row')
      }

      this.loading = false
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
      }
    },
    deleteRow(rowId) {
      const i = this.rows.findIndex((u) => u[this.rowIdKey] === rowId)
      this.rows.splice(i, 1)
    },
    refresh() {
      this.fetch(this.page)
    },
  },
}
</script>
