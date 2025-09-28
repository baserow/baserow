import Vue from 'vue'
import _ from 'lodash'
import moment from '@baserow/modules/core/moment'
import { clone } from '@baserow/modules/core/utils/object'
import { GroupTaskQueue } from '@baserow/modules/core/utils/queue'
import ViewService from '@baserow/modules/database/services/view'
import CalendarService from '@baserow_premium/services/views/calendar'
import {
  calculateSingleRowSearchMatches,
  extractRowMetadata,
  getFilters,
  getRowSortFunction,
  matchSearchFilters,
} from '@baserow/modules/database/utils/view'
import RowService from '@baserow/modules/database/services/row'
import {
  getMonthlyTimestamps,
  getUserTimeZone,
} from '@baserow/modules/core/utils/date'
import {
  extractChangedFields,
  getRowMetadata,
  prepareNewOldAndUpdateRequestValues,
  prepareRowForRequest,
  updateRowMetadataType,
} from '@baserow/modules/database/utils/row'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'

export function populateRow(row, metadata = {}, fullyLoaded = true) {
  row._ = {
    metadata: getRowMetadata(row, metadata),
    // Whether the row should be displayed based on the current activeSearchTerm term.
    matchSearch: true,
    // Contains the specific field ids which match the activeSearchTerm term.
    // Could be empty even when matchSearch is true when there is no
    // activeSearchTerm term applied.
    fieldSearchMatches: [],
    fetching: false,
    fullyLoaded,
  }
  return row
}

export function populateDateStack(stack, data) {
  Object.assign(stack, {
    loading: false,
  })
  stack.results.forEach((row) => {
    const metadata = extractRowMetadata(data, row.id)
    populateRow(row, metadata, false)
  })
  return stack
}

const updateRowQueue = new GroupTaskQueue()

export const state = () => ({
  loading: false,
  loadingRows: false,
  // The calendar view id that is being displayed
  lastCalendarId: null,
  // The chosen date field that the
  // items will be organized by in the view
  dateFieldId: null,
  fieldOptions: {},
  // dateStack organizes rows by dates (2023-02-21)
  // based on the date field with dateFieldId
  dateStacks: {},
  // How many items per date are fetched
  bufferRequestSize: 10,
  // Determines currently selected time period
  // based on a specific date. For example, if selectedDate
  // is today, the calendar view will be showing the
  // current month surrounding it.
  // It is an instance of moment.
  selectedDate: null,
  // A user provided optional search term which can be used to filter down rows.
  activeSearchTerm: '',
  // If true then the activeSearchTerm will be sent to the server to filter rows
  // entirely out. When false no server filter will be applied and rows which do not
  // have any matching cells will still be displayed.
  hideRowsNotMatchingSearch: true,
  adhocFiltering: false,
  // Indicates whether row(s) are currently being created.
  creating: false,
})

export const mutations = {
  RESET(state) {
    state.loadingRows = false
    state.lastCalendarId = null
    state.dateFieldId = null
    state.fieldOptions = {}
    state.dateStacks = {}
    state.activeSearchTerm = ''
    state.hideRowsNotMatchingSearch = true
    state.adhocFiltering = false
  },
  SET_SEARCH(state, { activeSearchTerm, hideRowsNotMatchingSearch }) {
    state.activeSearchTerm = activeSearchTerm.trim()
    state.hideRowsNotMatchingSearch = hideRowsNotMatchingSearch
  },
  SET_LOADING_ROWS(state, loading) {
    state.loadingRows = loading
  },
  SET_ROW_LOADING(state, { row, value }) {
    Vue.set(row._, 'loading', value)
  },
  SET_ROW_SEARCH_MATCHES(state, { row, matchSearch }) {
    row._.matchSearch = matchSearch
  },
  SET_LAST_CALENDAR_ID(state, calendarId) {
    state.lastCalendarId = calendarId
  },
  SET_DATE_FIELD_ID(state, dateFieldId) {
    state.dateFieldId = dateFieldId
  },
  SET_SELECTED_DATE(state, selectedDate) {
    // Store as a unix timestamp so the serialization from Nuxt -> Client works as
    // you can't safely serialize and transmit an entire moment object.
    state.selectedDate = selectedDate.valueOf()
  },
  REPLACE_ALL_DATE_STACKS(state, stacks) {
    state.dateStacks = stacks
  },
  ADD_ROWS_TO_STACK(state, { date, count, rows }) {
    if (count) {
      state.dateStacks[date].count = count
    }
    state.dateStacks[date].results.push(...rows)
  },
  ADD_STACK(state, { date, stack }) {
    Vue.set(state.dateStacks, date, stack)
  },
  REPLACE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = fieldOptions
  },
  UPDATE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = _.merge({}, state.fieldOptions, fieldOptions)
  },
  UPDATE_FIELD_OPTIONS_OF_FIELD(state, { fieldId, values }) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      Object.assign(state.fieldOptions[fieldId], values)
    } else {
      state.fieldOptions = Object.assign({}, state.fieldOptions, {
        [fieldId]: values,
      })
    }
  },
  DELETE_FIELD_OPTIONS(state, fieldId) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      delete state.fieldOptions[fieldId]
    }
  },
  ADD_FIELD_TO_ALL_ROWS(state, { field, value }) {
    const name = `field_${field.id}`
    Object.keys(state.dateStacks).forEach((stack) => {
      // We have to replace all the rows by using the map function to make it
      // reactive and update immediately.
      state.dateStacks[stack].results = state.dateStacks[stack].results.map(
        (row) => {
          if (
            row !== null &&
            !Object.prototype.hasOwnProperty.call(row, name)
          ) {
            row[`field_${field.id}`] = value
            return { ...row }
          }
          return row
        }
      )
    })
  },
  CREATE_ROW(state, { row, stackId, index }) {
    state.dateStacks[stackId].results.splice(index, 0, row)
  },
  UPDATE_ROW(state, { row, values }) {
    let updated = false
    Object.keys(state.dateStacks).forEach((stack) => {
      const rows = state.dateStacks[stack].results
      const index = rows.findIndex((item) => item.id === row.id)
      if (index !== -1) {
        const existingRowState = rows[index]
        Object.assign(existingRowState, values)
        updated = true
      }
    })
    if (!updated) {
      Object.assign(row, values)
    }
  },
  UPDATE_VALUE_OF_ALL_ROWS_IN_STACK(state, { fieldId, stackId, values }) {
    const name = `field_${fieldId}`
    state.dateStacks[stackId].results.forEach((row) => {
      Object.assign(row[name], values)
    })
  },
  MOVE_ROW(
    state,
    { currentStackId, currentIndex, targetStackId, targetIndex }
  ) {
    state.dateStacks[targetStackId].results.splice(
      targetIndex,
      0,
      state.dateStacks[currentStackId].results.splice(currentIndex, 1)[0]
    )
  },
  DELETE_ROW(state, { stackId, index }) {
    state.dateStacks[stackId].results.splice(index, 1)
  },
  INCREASE_COUNT(state, { stackId }) {
    state.dateStacks[stackId].count++
  },
  DECREASE_COUNT(state, { stackId }) {
    state.dateStacks[stackId].count--
  },
  UPDATE_ROW_VALUES(state, { row, values }) {
    Object.assign(row, values)
  },
  UPDATE_ROW_METADATA(state, { row, rowMetadataType, updateFunction }) {
    updateRowMetadataType(row, rowMetadataType, updateFunction)
  },
  SET_ADHOC_FILTERING(state, adhocFiltering) {
    state.adhocFiltering = adhocFiltering
  },
  SET_ROW_FETCHING(state, { row, value }) {
    Object.keys(state.dateStacks).forEach((stack) => {
      const rows = state.dateStacks[stack].results
      const index = rows.findIndex((item) => item?.id === row.id)
      if (index !== -1) {
        const existingRowState = rows[index]
        existingRowState._.fetching = value
        existingRowState._.fullyLoaded = !value
      }
    })
  },
  SET_CREATING(state, value) {
    state.creating = value
  },
}

export const actions = {
  /**
   * Resets the store completely throwing away all state.
   */
  reset({ dispatch, commit, getters }, _) {
    commit('RESET')
  },
  /**
   * Resets the store completely throwing away all state and loads new rows given
   * a new view etc.
   * rows.
   */
  async resetAndFetchInitial(
    { dispatch, commit, getters },
    {
      calendarId,
      dateFieldId,
      fields,
      includeFieldOptions = true,
      adhocFiltering,
    }
  ) {
    commit('RESET')
    await dispatch('refreshAndFetchInitial', {
      calendarId,
      dateFieldId,
      fields,
      includeFieldOptions,
      adhocFiltering,
    })
  },
  /**
   * Refreshes the store given new date and view parameters and then refetches the
   * rows. Doesn't throw away field options etc.
   */
  async refreshAndFetchInitial(
    { dispatch, commit, getters },
    {
      calendarId,
      dateFieldId,
      fields,
      includeFieldOptions = true,
      adhocFiltering,
    }
  ) {
    commit('SET_DATE_FIELD_ID', dateFieldId)
    commit('SET_LAST_CALENDAR_ID', calendarId)
    commit('SET_ADHOC_FILTERING', adhocFiltering)
    await dispatch('fetchInitial', {
      includeFieldOptions,
      fields,
    })
  },
  /**
   * Fetches an initial set of rows and adds that data to the store.
   */
  async fetchInitial(
    { dispatch, commit, getters },
    { fields, includeFieldOptions = true }
  ) {
    // We can't guess the users timezone when doing the server side render.
    // So we only can know what today is and load rows in the client side when the
    // field does not have a forced timezone.
    if (!process.server || getters.getFieldTimeZoneIfSet(fields)) {
      const timezone = getters.getTimeZone(fields)
      const todayOrSelectedDay =
        getters.getSelectedDate(fields) == null
          ? moment.tz(timezone)
          : getters.getSelectedDate(fields)
      await dispatch('fetchMonthly', {
        dateTime: todayOrSelectedDay,
        fields,
        includeFieldOptions,
      })
    }
  },
  /**
   * Fetches a set of rows based on the provided datetime.
   */
  async fetchMonthly(
    { commit, getters, rootGetters },
    { dateTime, fields, includeFieldOptions = false }
  ) {
    const calendarId = getters.getLastCalendarId
    commit('SET_SELECTED_DATE', dateTime)

    const df = getters.getDateField(fields)
    if (
      !df ||
      this.$registry.get('field', df.type).canRepresentDate(df) === false
    ) {
      commit('RESET')
      return
    }

    commit('SET_LOADING_ROWS', true)
    const { fromTimestamp, toTimestamp } = getMonthlyTimestamps(dateTime)
    const view = rootGetters['view/get'](getters.getLastCalendarId)
    const filters = getFilters(view, getters.getAdhocFiltering)

    try {
      const { data } = await CalendarService(this.$client).fetchRows({
        calendarId: getters.getLastCalendarId,
        limit: getters.getBufferRequestSize,
        offset: 0,
        includeFieldOptions,
        fromTimestamp,
        toTimestamp,
        userTimeZone: getUserTimeZone(),
        search: getters.getServerSearchTerm,
        searchMode: getDefaultSearchModeFromEnv(this.$config),
        filters,
        publicUrl: rootGetters['page/view/public/getIsPublic'],
        publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      })
      // Don't do anything if the calendarId does not match the current view calendarId
      // because that probably means the user switched to another view or table, and
      // the data that is returned here shouldn't do anything.
      if (calendarId !== getters.getLastCalendarId) {
        return
      }
      const lastRequest = dateTime.isSame(getters.getSelectedDate(fields))
      if (lastRequest) {
        Object.keys(data.rows).forEach((key) => {
          populateDateStack(data.rows[key], data)
        })
        commit('REPLACE_ALL_DATE_STACKS', data.rows)
        if (includeFieldOptions) {
          commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options)
        }
        commit('SET_LOADING_ROWS', false)
      }
    } catch (error) {
      if (error.handler.code === 'ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD') {
        commit('RESET')
      } else {
        throw error
      }
    } finally {
      const lastRequest = dateTime.isSame(getters.getSelectedDate(fields))
      if (lastRequest) {
        commit('SET_LOADING_ROWS', false)
      }
    }
  },
  /**
   * This action is called when the users scrolls to the end of the stack. Because
   * we don't fetch all the rows, the next set will be fetched when the user reaches
   * the end.
   */
  async fetchMore(
    { dispatch, commit, getters, rootGetters },
    { date, fields }
  ) {
    const calendarId = getters.getLastCalendarId
    const stack = getters.getDateStack(date)
    const rows = stack.results
    const timezone = getters.getTimeZone(fields)
    const fromTimestamp = moment.tz(date, timezone)
    const toTimestamp = moment.tz(fromTimestamp, timezone).add(1, 'day')
    const view = rootGetters['view/get'](calendarId)
    const filters = getFilters(view, getters.getAdhocFiltering)
    const { data } = await CalendarService(this.$client).fetchRows({
      calendarId,
      limit: getters.getBufferRequestSize,
      offset: rows.length,
      includeFieldOptions: false,
      fromTimestamp,
      toTimestamp,
      userTimeZone: getUserTimeZone(),
      search: getters.getServerSearchTerm,
      searchMode: getDefaultSearchModeFromEnv(this.$config),
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      filters,
    })
    // Don't do anything if the calendarId does not match the current view calendarId
    // because that probably means the user switched to another view or table, and
    // the data that is returned here shouldn't do anything.
    if (calendarId !== getters.getLastCalendarId) {
      return
    }
    const newRows = data.rows[date].results
    const newCount = data.rows[date].count
    newRows.forEach((row) => {
      const metadata = extractRowMetadata(data, row.id)
      populateRow(row, metadata, false)
    })
    commit('ADD_ROWS_TO_STACK', { date, count: newCount, rows: newRows })
    dispatch('updateSearch', { fields })
  },
  /**
   * Updates the field options of a given field in the store. So no API request to
   * the backend is made.
   */
  setFieldOptionsOfField({ commit }, { field, values }) {
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })
  },
  /**
   * Replaces all field options with new values and also makes an API request to the
   * backend with the changed values. If the request fails the action is reverted.
   */
  async updateAllFieldOptions(
    { dispatch, getters, rootGetters },
    { newFieldOptions, oldFieldOptions, readOnly = false }
  ) {
    dispatch('forceUpdateAllFieldOptions', newFieldOptions)

    const calendarId = getters.getLastCalendarId
    if (!readOnly) {
      const updateValues = { field_options: newFieldOptions }

      try {
        await ViewService(this.$client).updateFieldOptions({
          viewId: calendarId,
          values: updateValues,
        })
      } catch (error) {
        dispatch('forceUpdateAllFieldOptions', oldFieldOptions)
        throw error
      }
    }
  },
  /**
   * Forcefully updates all field options without making a call to the backend.
   */
  forceUpdateAllFieldOptions({ commit }, fieldOptions) {
    commit('UPDATE_ALL_FIELD_OPTIONS', fieldOptions)
  },
  /**
   * Deletes the field options of the provided field id if they exist.
   */
  forceDeleteFieldOptions({ commit }, fieldId) {
    commit('DELETE_FIELD_OPTIONS', fieldId)
  },
  /**
   * Updates the order of all the available field options. The provided order parameter
   * should be an array containing the field ids in the correct order.
   */
  async updateFieldOptionsOrder(
    { commit, getters, dispatch },
    { order, readOnly = false }
  ) {
    const oldFieldOptions = clone(getters.getAllFieldOptions)
    const newFieldOptions = clone(getters.getAllFieldOptions)

    // Update the order of the field options that have not been provided in the order.
    // They will get a position that places them after the provided field ids.
    let i = 0
    Object.keys(newFieldOptions).forEach((fieldId) => {
      if (!order.includes(parseInt(fieldId))) {
        newFieldOptions[fieldId].order = order.length + i
        i++
      }
    })

    // Update create the field options and set the correct order value.
    order.forEach((fieldId, index) => {
      const id = fieldId.toString()
      if (Object.prototype.hasOwnProperty.call(newFieldOptions, id)) {
        newFieldOptions[fieldId.toString()].order = index
      }
    })

    return await dispatch('updateAllFieldOptions', {
      oldFieldOptions,
      newFieldOptions,
      readOnly,
    })
  },
  /**
   * Updates the field options of a specific field.
   */
  async updateFieldOptionsOfField(
    { commit, getters, rootGetters },
    { view, field, values, readOnly = false, undoRedoActionGroupId = null }
  ) {
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })

    if (!readOnly) {
      const calendarId = getters.getLastCalendarId
      const oldValues = clone(getters.getAllFieldOptions[field.id])
      const updateValues = { field_options: {} }
      updateValues.field_options[field.id] = values

      try {
        await ViewService(this.$client).updateFieldOptions({
          viewId: calendarId,
          values: updateValues,
          undoRedoActionGroupId,
        })
      } catch (error) {
        commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
          fieldId: field.id,
          values: oldValues,
        })
        throw error
      }
    }
  },
  /**
   * Creates a new row and adds it to the state if needed.
   */
  async createNewRow(
    { dispatch, commit, getters },
    { view, table, fields, values }
  ) {
    const preparedRow = prepareRowForRequest(values, fields, this.$registry)

    commit('SET_CREATING', true)
    const { data } = await RowService(this.$client).create(
      table.id,
      preparedRow,
      null,
      getters.getLastCalendarId
    )
    commit('SET_CREATING', false)
    return await dispatch('createdNewRow', {
      view,
      values: data,
      fields,
    })
  },
  /**
   * Can be called when a new row has been created. This action will make sure that
   * the state is updated accordingly. If the newly created position is within the
   * current buffer (`dateStack.results`), then it will be added there, otherwise, just
   * the count is increased.
   *
   * @param values  The values of the newly created row.
   * @param row     Can be provided when the row already existed within the state.
   *                In that case, the `_` data will be preserved. Can be useful when
   *                a row has been updated while being dragged.
   */
  async createdNewRow(
    { dispatch, commit, getters, rootGetters },
    { view, values, fields }
  ) {
    const row = clone(values)
    populateRow(row)
    const matchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row,
      fields,
    })
    dispatch('updateSearchMatchesForRow', { row, fields })

    if (!matchesFilters || !row._.matchSearch) {
      return
    }

    const dateFieldId = getters.getDateFieldIdIfNotTrashed(fields)
    const value = row[`field_${dateFieldId}`]
    const timezone = getters.getTimeZone(fields)
    const stackId = moment.tz(value, timezone).format('YYYY-MM-DD')
    const stack = getters.getDateStack(stackId)
    if (stack === undefined) {
      return
    }
    const sortings = [
      {
        field: dateFieldId,
        value: 'ASC',
        order: 'ASC',
        type: DEFAULT_SORT_TYPE_KEY,
      },
    ]
    const sortedRows = clone(stack.results)
    sortedRows.push(row)
    sortedRows.sort(getRowSortFunction(this.$registry, sortings, fields))
    const index = sortedRows.findIndex((r) => r.id === row.id)
    const isLast = index === sortedRows.length - 1

    // Because we don't fetch all the rows from the backend, we can't know for sure
    // whether or not the row is being added at the right position. Therefore, if
    // it's last, we just not add it to the store and wait for the user to fetch the
    // next page.
    if (!isLast || stack.results.length === stack.count) {
      commit('CREATE_ROW', { row, stackId, index })
    }
    // We always need to increase the count whether row has been added to the store
    // or not because the count is for all the rows and not just the ones in the store.
    commit('INCREASE_COUNT', { stackId })
  },
  /**
   * Called when the user wants to delete an existing row in the table.
   */
  async deleteRow({ commit, dispatch, getters }, { table, view, row, fields }) {
    commit('SET_ROW_LOADING', { row, value: true })

    try {
      await dispatch('deletedExistingRow', {
        view,
        fields,
        row,
      })
      await RowService(this.$client).delete(
        table.id,
        row.id,
        getters.getLastCalendarId
      )
    } catch (error) {
      await dispatch('createdNewRow', {
        view,
        values: row,
        fields,
      })
      commit('SET_ROW_LOADING', { row, value: false })
      throw error
    }
  },

  /**
   * Can be called when a row in the table has been deleted. This action will make
   * sure that the state is updated accordingly.
   */
  async deletedExistingRow(
    { dispatch, commit, getters },
    { view, row, fields }
  ) {
    row = clone(row)
    populateRow(row)
    dispatch('updateSearchMatchesForRow', { row, fields })

    const matchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row,
      fields,
    })
    if (!matchesFilters || !row._.matchSearch) {
      return
    }

    const dateFieldId = getters.getDateFieldIdIfNotTrashed(fields)
    const value = row[`field_${dateFieldId}`]
    const timezone = getters.getTimeZone(fields)
    const stackId = value
      ? moment.tz(value, timezone).format('YYYY-MM-DD')
      : null
    const stack = getters.getDateStack(stackId)
    const current = getters.findStackIdAndIndex(row.id)
    if (current !== undefined) {
      const currentStackId = current[0]
      const currentIndex = current[1]
      const currentRow = current[2]
      commit('DELETE_ROW', { stackId: currentStackId, index: currentIndex })
      commit('DECREASE_COUNT', { stackId: currentStackId })
      return currentRow
    } else if (stack) {
      commit('DECREASE_COUNT', { stackId })
    }

    return null
  },
  /**
   * Can be called when a row in the table has been updated. This action will make sure
   * that the state is updated accordingly. If the date field value has
   * changed, the row will be moved to the right stack. If the position has changed,
   * it will be moved to the right position.
   */
  async updatedExistingRow(
    { dispatch, getters, commit },
    { view, row, values, fields }
  ) {
    const dateFieldId = getters.getDateFieldIdIfNotTrashed(fields)
    const fieldName = `field_${dateFieldId}`

    // First, we virtually need to figure out if the row was in the old stack.
    const oldRow = populateRow(clone(row))
    const oldRowMatchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row: oldRow,
      fields,
    })
    dispatch('updateSearchMatchesForRow', { row: oldRow, fields })

    const oldValue = oldRow[fieldName]
    const timezone = getters.getTimeZone(fields)
    const oldStackId = moment.tz(oldValue, timezone).format('YYYY-MM-DD')
    const oldStack = getters.getDateStack(oldStackId)
    let oldExists = false
    let oldExistingIndex = -1
    if (oldStack) {
      const oldStackResults = clone(oldStack.results)
      oldExistingIndex = oldStackResults.findIndex((r) => r.id === oldRow.id)
      oldExists =
        oldExistingIndex > -1 && oldRowMatchesFilters && oldRow._.matchSearch
    }

    // Second, we need to figure out if the row should be visible in the new stack.
    const newRow = Object.assign(populateRow(clone(row)), values)
    const newRowMatchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row: newRow,
      fields,
    })
    dispatch('updateSearchMatchesForRow', { row: newRow, fields })

    const newValue = newRow[fieldName]
    const newStackId = moment.tz(newValue, timezone).format('YYYY-MM-DD')
    const newStack = getters.getDateStack(newStackId)
    let newExists = false
    let newIndex = -1
    if (newStack) {
      const newStackResults = newStack ? clone(newStack.results) : []
      const newRowCurrentIndex = newStackResults.findIndex(
        (r) => r.id === newRow.id
      )
      let newStackCount = newStack.count
      if (newRowCurrentIndex > -1) {
        newStackResults.splice(newRowCurrentIndex, 1)
        newStackCount--
      }
      newStackResults.push(newRow)
      newStackCount++
      const sortings = [
        {
          field: dateFieldId,
          value: 'ASC',
          order: 'ASC',
          type: DEFAULT_SORT_TYPE_KEY,
        },
      ]
      newStackResults.sort(getRowSortFunction(this.$registry, sortings, fields))
      newIndex = newStackResults.findIndex((r) => r.id === newRow.id)
      const newIsLast = newIndex === newStackResults.length - 1
      newExists =
        (!newIsLast || newStackResults.length === newStackCount) &&
        newRowMatchesFilters &&
        newRow._.matchSearch
    }

    commit('UPDATE_ROW', { row, values })

    if (oldExists && newExists) {
      commit('MOVE_ROW', {
        currentStackId: oldStackId,
        currentIndex: oldExistingIndex,
        targetStackId: newStackId,
        targetIndex: newIndex,
      })
      commit('DECREASE_COUNT', { stackId: oldStackId })
      commit('INCREASE_COUNT', { stackId: newStackId })
    } else if (oldExists && !newExists) {
      commit('DELETE_ROW', { stackId: oldStackId, index: oldExistingIndex })
      commit('DECREASE_COUNT', { stackId: oldStackId })
    } else if (!oldExists && newExists) {
      commit('CREATE_ROW', {
        row: newRow,
        stackId: newStackId,
        index: newIndex,
      })
      commit('INCREASE_COUNT', { stackId: newStackId })
    }
  },
  /**
   * Check if the provided row matches the provided view filters.
   */
  rowMatchesFilters(context, { view, fields, row, overrides = {} }) {
    const values = JSON.parse(JSON.stringify(row))
    Object.assign(values, overrides)

    // The value is always valid if the filters are disabled.
    return view.filters_disabled
      ? true
      : matchSearchFilters(
          this.$registry,
          view.filter_type,
          view.filters,
          view.filter_groups,
          fields,
          values
        )
  },
  /**
   * Updates the value of a row and make the changes to the store accordingly.
   */
  async updateRowValue(
    { commit, dispatch, getters, state },
    { view, table, row, field, fields, value, oldValue }
  ) {
    const { newRowValues, oldRowValues, updateRequestValues } =
      prepareNewOldAndUpdateRequestValues(
        row,
        fields,
        field,
        value,
        oldValue,
        this.$registry
      )

    dispatch('updateSearchMatchesForRow', { row, fields })

    await dispatch('updatedExistingRow', {
      view,
      row,
      values: newRowValues,
      fields,
    })
    // There is a chance that the row is not in the buffer, but it does exist in
    // the view. In that case, the `updatedExistingRow` action has not done
    // anything. There is a possibility that the row is visible in the row edit
    // modal, but then it won't be updated, so we have to update it forcefully.
    commit('UPDATE_ROW_VALUES', {
      row,
      values: { ...newRowValues },
    })

    try {
      // Add the update actual update function to the queue so that the same row
      // will never be updated concurrency, and so that the value won't be
      // updated if the row hasn't been created yet.
      await updateRowQueue.add(async () => {
        const updateRowsData = [
          Object.assign({ id: row.id }, updateRequestValues),
        ]
        const { data } = await RowService(this.$client).batchUpdate(
          table.id,
          updateRowsData,
          null,
          getters.getLastCalendarId
        )
        const updatedFieldIds = data.metadata?.updated_field_ids || []

        const readOnlyData = extractChangedFields(
          data.items[0],
          fields,
          updatedFieldIds,
          this.$registry
        )

        // One of fields updated is our date field, so the row should be checked if
        // it should be moved to another date.
        const dateFieldId = state.dateFieldId

        if (updatedFieldIds.includes(dateFieldId)) {
          await dispatch('updatedExistingRow', {
            view,
            row,
            values: readOnlyData,
            fields,
          })
        } else {
          commit('UPDATE_ROW', { row, values: readOnlyData })
        }
      }, row.id)
    } catch (error) {
      await dispatch('updatedExistingRow', {
        view,
        row,
        values: oldRowValues,
        fields,
      })
      commit('UPDATE_ROW_VALUES', {
        row,
        values: { ...oldRowValues },
      })
      throw error
    }
  },
  /**
   * Used when row data needs to be directly re-fetched from the Backend and
   * the other (background) row needs to be refreshed. For example, when editing
   * row from a *different* table using ForeignRowEditModal or just RowEditModal
   * component in general.
   */
  async refreshRowFromBackend(
    { commit, getters, rootGetters },
    { table, row }
  ) {
    const gridId = getters.getLastCalendarId
    const publicUrl = rootGetters['page/view/public/getIsPublic']
    const publicAuthToken = rootGetters['page/view/public/getAuthToken']
    commit('SET_ROW_FETCHING', { row, value: true })
    try {
      const { data } = await ViewService(this.$client).fetchRow(
        table.id,
        row.id,
        gridId,
        publicUrl,
        publicAuthToken
      )
      // Use the return value to update the desired row with latest values from the
      // backend.
      commit('UPDATE_ROW', { row, values: data })
    } finally {
      commit('SET_ROW_FETCHING', { row, value: false })
    }
  },
  /**
   * Adds a field with a provided value to the rows in the store. This will for
   * example be called when a new field has been created.
   */
  addField({ commit }, { field, value = null }) {
    commit('ADD_FIELD_TO_ALL_ROWS', { field, value })
  },
  selectDateAndStartLoading({ commit }, { selectedDate }) {
    commit('SET_LOADING_ROWS', true)
    commit('SET_SELECTED_DATE', selectedDate)
  },
  async selectRow({ commit, getters, dispatch }, { row, fields }) {
    const dateFieldId = getters.getDateFieldIdIfNotTrashed(fields)
    if (dateFieldId) {
      const value = row[`field_${dateFieldId}`]
      const dateTime = moment.tz(value, getters.getTimeZone(fields))
      const {
        fromTimestamp: currentFromTimestamp,
        toTimestamp: currentToTimestamp,
      } = getMonthlyTimestamps(getters.getSelectedDate(fields))
      // Selecting a new row might be triggered by a navigation to a
      // `calendar/ABC/row/XYZ` URL or by the user clicking on a row they can see
      // in the calendar view. When triggered by a navigation we almost certainly don't
      // right month loaded into the store and so if we don't we fetch all the other
      // rows for that month.
      if (
        !dateTime.isBetween(
          currentFromTimestamp,
          currentToTimestamp,
          null,
          '[]'
        )
      ) {
        await dispatch('fetchMonthly', {
          dateTime,
          fields,
        })
      }
    }
  },
  updateSearch(
    { commit, dispatch, getters, state },
    {
      fields,
      activeSearchTerm = state.activeSearchTerm,
      hideRowsNotMatchingSearch = state.hideRowsNotMatchingSearch,
      refreshMatchesOnClient = true,
    }
  ) {
    commit('SET_SEARCH', { activeSearchTerm, hideRowsNotMatchingSearch })
    if (refreshMatchesOnClient) {
      getters.getAllRows.forEach((row) =>
        dispatch('updateSearchMatchesForRow', {
          row,
          fields,
          forced: true,
        })
      )
    }
  },
  updateSearchMatchesForRow(
    { commit, getters, rootGetters },
    { row, fields = null, overrides, forced = false }
  ) {
    // Avoid computing search on table loading
    if (getters.getActiveSearchTerm || forced) {
      const rowSearchMatches = calculateSingleRowSearchMatches(
        row,
        getters.getActiveSearchTerm,
        getters.isHidingRowsNotMatchingSearch,
        fields,
        this.$registry,
        getDefaultSearchModeFromEnv(this.$config),
        overrides
      )
      commit('SET_ROW_SEARCH_MATCHES', rowSearchMatches)
    }
  },
  /**
   * Updates a single row's row._.metadata based on the provided rowMetadataType and
   * updateFunction.
   */
  updateRowMetadata(
    { commit, getters },
    { rowId, rowMetadataType, updateFunction }
  ) {
    const target = getters.findStackIdAndIndex(rowId)
    if (target !== undefined) {
      const row = target[2]
      commit('UPDATE_ROW_METADATA', { row, rowMetadataType, updateFunction })
    }
  },
}

export const getters = {
  getServerSearchTerm(state) {
    return state.activeSearchTerm
  },
  getActiveSearchTerm(state) {
    return state.activeSearchTerm
  },
  isHidingRowsNotMatchingSearch(state) {
    return state.hideRowsNotMatchingSearch
  },
  getLoadingRows(state) {
    return state.loadingRows
  },
  getLastCalendarId(state) {
    return state.lastCalendarId
  },
  getDateFieldIdIfNotTrashed: (state, getters) => (fields) => {
    return getters.getDateField(fields)?.id
  },
  getAllFieldOptions(state) {
    return state.fieldOptions
  },
  getDateStack: (state) => (date) => {
    return state.dateStacks[date]
  },
  getBufferRequestSize(state) {
    return state.bufferRequestSize
  },
  getSelectedDate: (state, getters) => (fields) => {
    return state.selectedDate
      ? moment(state.selectedDate).tz(getters.getTimeZone(fields))
      : null
  },
  getAllRows(state) {
    let rows = []
    Object.keys(state.dateStacks).forEach((key) => {
      rows = rows.concat(state.dateStacks[key].results)
    })
    return rows
  },
  findStackIdAndIndex: (state) => (rowId) => {
    const stacks = state.dateStacks
    const keys = Object.keys(stacks)
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i]
      const results = stacks[key].results
      for (let i2 = 0; i2 < results.length; i2++) {
        const result = results[i2]
        if (result.id === rowId) {
          return [key, i2, result]
        }
      }
    }
  },
  getDateField: (state) => (fields) => {
    const fieldId = state.dateFieldId
    if (fieldId) {
      return fields.find((field) => field.id === fieldId)
    } else {
      return null
    }
  },
  getFieldTimeZoneIfSet: (state, getters) => (fields) => {
    const dateField = getters.getDateField(fields)
    if (dateField?.date_include_time) {
      return dateField?.date_force_timezone
    } else {
      return 'UTC'
    }
  },
  getTimeZone: (state, getters) => (fields) => {
    const fieldTimezone = getters.getFieldTimeZoneIfSet(fields)
    return fieldTimezone || getUserTimeZone()
  },
  getCalendarTimezoneAndDateLoaded: (state, getters) => (fields) => {
    return getters.getSelectedDate(fields) != null
  },
  getAdhocFiltering(state) {
    return state.adhocFiltering
  },
  getCreating(state) {
    return state.creating
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
