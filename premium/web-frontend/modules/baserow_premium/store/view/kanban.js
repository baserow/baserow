import Vue from 'vue'
import _ from 'lodash'
import { clone } from '@baserow/modules/core/utils/object'
import { GroupTaskQueue } from '@baserow/modules/core/utils/queue'
import ViewService from '@baserow/modules/database/services/view'
import KanbanService from '@baserow_premium/services/views/kanban'
import {
  extractRowMetadata,
  getFilters,
  getRowSortFunction,
  matchSearchFilters,
} from '@baserow/modules/database/utils/view'
import RowService from '@baserow/modules/database/services/row'
import FieldService from '@baserow/modules/database/services/field'
import { SingleSelectFieldType } from '@baserow/modules/database/fieldTypes'
import {
  extractChangedFields,
  getRowMetadata,
  prepareNewOldAndUpdateRequestValues,
  prepareRowForRequest,
  updateRowMetadataType,
} from '@baserow/modules/database/utils/row'

export function populateRow(row, metadata = {}, fullyLoaded = true) {
  row._ = {
    metadata: getRowMetadata(row, metadata),
    dragging: false,
    fetching: false,
    fullyLoaded,
  }
  return row
}

export function populateStack(stack, data) {
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
  lastKanbanId: -1,
  singleSelectFieldId: -1,
  stacks: {},
  fieldOptions: {},
  bufferRequestSize: 24,
  draggingRow: null,
  draggingOriginalStackId: null,
  draggingOriginalBefore: null,
  // If true, ad hoc filtering is used instead of persistent one
  adhocFiltering: false,
  // Indicates whether row(s) are currently being created.
  creating: false,
})

export const mutations = {
  RESET(state) {
    state.lastKanbanId = -1
    state.singleSelectFieldId = -1
    state.stacks = {}
    state.fieldOptions = {}
  },
  SET_LAST_KANBAN_ID(state, kanbanId) {
    state.lastKanbanId = kanbanId
  },
  SET_SINGLE_SELECT_FIELD_ID(state, singleSelectFieldId) {
    state.singleSelectFieldId = singleSelectFieldId
  },
  SET_ROW_LOADING(state, { row, value }) {
    Vue.set(row._, 'loading', value)
  },
  REPLACE_ALL_STACKS(state, stacks) {
    state.stacks = stacks
  },
  ADD_ROWS_TO_STACK(state, { selectOptionId, count, rows }) {
    if (count) {
      state.stacks[selectOptionId].count = count
    }
    state.stacks[selectOptionId].results.push(...rows)
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
  ADD_STACK(state, { id, stack }) {
    Vue.set(state.stacks, id.toString(), stack)
  },
  START_ROW_DRAG(state, { row, currentStackId, currentBefore }) {
    row._.dragging = true
    state.draggingRow = row
    state.draggingOriginalStackId = currentStackId
    state.draggingOriginalBefore = currentBefore
  },
  STOP_ROW_DRAG(state, { row }) {
    row._.dragging = false
    state.draggingRow = null
    state.draggingOriginalStackId = null
    state.draggingOriginalBefore = null
  },
  CREATE_ROW(state, { row, stackId, index }) {
    state.stacks[stackId].results.splice(index, 0, row)
  },
  DELETE_ROW(state, { stackId, index }) {
    state.stacks[stackId].results.splice(index, 1)
  },
  INCREASE_COUNT(state, { stackId }) {
    state.stacks[stackId].count++
  },
  DECREASE_COUNT(state, { stackId }) {
    state.stacks[stackId].count--
  },
  UPDATE_ROW(state, { row, values }) {
    let updated = false
    Object.keys(state.stacks).forEach((stack) => {
      const rows = state.stacks[stack].results
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
    state.stacks[stackId].results.forEach((row) => {
      Object.assign(row[name], values)
    })
  },
  MOVE_ROW(
    state,
    { currentStackId, currentIndex, targetStackId, targetIndex }
  ) {
    state.stacks[targetStackId].results.splice(
      targetIndex,
      0,
      state.stacks[currentStackId].results.splice(currentIndex, 1)[0]
    )
    if (currentStackId !== targetStackId) {
      state.stacks[currentStackId].count--
      state.stacks[targetStackId].count++
    }
  },
  ADD_FIELD_TO_ALL_ROWS(state, { field, value }) {
    const name = `field_${field.id}`
    Object.keys(state.stacks).forEach((stack) => {
      // We have to replace all the rows by using the map function to make it
      // reactive and update immediately. If we don't do this, the value in the
      // field components of the grid and modal don't always have the correct value
      // binding.
      state.stacks[stack].results = state.stacks[stack].results.map((row) => {
        if (row !== null && !Object.prototype.hasOwnProperty.call(row, name)) {
          row[`field_${field.id}`] = value
          return { ...row }
        }
        return row
      })
    })
  },
  UPDATE_ROW_VALUES(state, { row, values }) {
    Object.assign(row, values)
  },
  SET_ROW_FETCHING(state, { row, value }) {
    Object.keys(state.stacks).forEach((stack) => {
      const rows = state.stacks[stack].results
      const index = rows.findIndex((item) => item?.id === row.id)
      if (index !== -1) {
        const existingRowState = rows[index]
        existingRowState._.fetching = value
        existingRowState._.fullyLoaded = !value
      }
    })
  },
  UPDATE_ROW_METADATA(state, { row, rowMetadataType, updateFunction }) {
    updateRowMetadataType(row, rowMetadataType, updateFunction)
  },
  SET_ADHOC_FILTERING(state, adhocFiltering) {
    state.adhocFiltering = adhocFiltering
  },
  SET_CREATING(state, value) {
    state.creating = value
  },
}

export const actions = {
  /**
   * This method is typically called when the kanban view loads, but when it doesn't
   * yet have a single select option field. This will make sure that the old state
   * of another kanban view will be reset.
   */
  reset({ commit }) {
    commit('RESET')
  },
  /**
   * Fetches an initial set of rows and adds that data to the store.
   */
  async fetchInitial(
    { dispatch, commit, getters, rootGetters },
    {
      kanbanId,
      singleSelectFieldId,
      adhocFiltering,
      includeFieldOptions = true,
    }
  ) {
    commit('SET_ADHOC_FILTERING', adhocFiltering)
    commit('SET_LAST_KANBAN_ID', kanbanId)
    const view = rootGetters['view/get'](kanbanId)
    const { data } = await KanbanService(this.$client).fetchRows({
      kanbanId,
      limit: getters.getBufferRequestSize,
      offset: 0,
      includeFieldOptions,
      selectOptions: [],
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      filters: getFilters(view, adhocFiltering),
    })
    // Don't do anything if the kanbanId does not match the current view kanbanId
    // because that probably means the user switched to another view or table, and
    // the data that is returned here shouldn't do anything.
    if (kanbanId !== getters.getLastKanbanId) {
      return
    }
    Object.keys(data.rows).forEach((key) => {
      populateStack(data.rows[key], data)
    })
    commit('SET_SINGLE_SELECT_FIELD_ID', singleSelectFieldId)
    commit('REPLACE_ALL_STACKS', data.rows)
    if (includeFieldOptions) {
      commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options)
    }
  },
  /**
   * This action is called when the users scrolls to the end of the stack. Because
   * we don't fetch all the rows, the next set will be fetched when the user reaches
   * the end.
   */
  async fetchMore(
    { dispatch, commit, getters, rootGetters },
    { selectOptionId }
  ) {
    const kanbanId = getters.getLastKanbanId
    const stack = getters.getStack(selectOptionId)
    const view = rootGetters['view/get'](kanbanId)
    const { data } = await KanbanService(this.$client).fetchRows({
      kanbanId,
      limit: getters.getBufferRequestSize,
      offset: 0,
      includeFieldOptions: false,
      selectOptions: [
        {
          id: selectOptionId,
          limit: getters.getBufferRequestSize,
          offset: stack.results.length,
        },
      ],
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      filters: getFilters(view, getters.getAdhocFiltering),
    })
    // Don't do anything if the kanbanId does not match the current view kanbanId
    // because that probably means the user switched to another view or table, and
    // the data that is returned here shouldn't do anything.
    if (kanbanId !== getters.getLastKanbanId) {
      return
    }
    const count = data.rows[selectOptionId].count
    const rows = data.rows[selectOptionId].results
    rows.forEach((row) => {
      const metadata = extractRowMetadata(data, row.id)
      populateRow(row, metadata, false)
    })
    commit('ADD_ROWS_TO_STACK', { selectOptionId, count, rows })
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
    { kanban, newFieldOptions, oldFieldOptions, readOnly = false }
  ) {
    dispatch('forceUpdateAllFieldOptions', newFieldOptions)

    const kanbanId = getters.getLastKanbanId
    if (!readOnly) {
      const updateValues = { field_options: newFieldOptions }

      try {
        await ViewService(this.$client).updateFieldOptions({
          viewId: kanbanId,
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
    { kanban, field, values, readOnly = false, undoRedoActionGroupId = null }
  ) {
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })

    if (!readOnly) {
      const kanbanId = getters.getLastKanbanId
      const oldValues = clone(getters.getAllFieldOptions[field.id])
      const updateValues = { field_options: {} }
      updateValues.field_options[field.id] = values

      try {
        await ViewService(this.$client).updateFieldOptions({
          viewId: kanbanId,
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
      getters.getLastKanbanId
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
   * current buffer (`stack.results`), then it will be added there, otherwise, just
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
    if (!matchesFilters) {
      return
    }

    const singleSelectFieldId = getters.getSingleSelectFieldId
    const option = row[`field_${singleSelectFieldId}`]
    const stackId = option !== null ? option.id : 'null'
    const stack = getters.getStack(stackId)

    const sortedRows = clone(stack.results)
    sortedRows.push(row)
    sortedRows.sort(getRowSortFunction(this.$registry, [], fields))
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
  async deleteExistingRow(
    { commit, dispatch, getters },
    { table, view, row, fields }
  ) {
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
        getters.getLastKanbanId
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

    const matchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row,
      fields,
    })
    if (!matchesFilters) {
      return
    }

    const singleSelectFieldId = getters.getSingleSelectFieldId
    const option = row[`field_${singleSelectFieldId}`]
    const stackId = option !== null ? option.id : 'null'
    const current = getters.findStackIdAndIndex(row.id)

    if (current !== undefined) {
      const currentStackId = current[0]
      const currentIndex = current[1]
      const currentRow = current[2]
      commit('DELETE_ROW', { stackId: currentStackId, index: currentIndex })
      commit('DECREASE_COUNT', { stackId: currentStackId })
      return currentRow
    } else {
      commit('DECREASE_COUNT', { stackId })
    }

    return null
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
   * Can be called when a row in the table has been updated. This action will make sure
   * that the state is updated accordingly. If the single select field value has
   * changed, the row will be moved to the right stack. If the position has changed,
   * it will be moved to the right position.
   */
  async updatedExistingRow(
    { dispatch, getters, commit },
    { view, row, values, fields }
  ) {
    const singleSelectFieldId = getters.getSingleSelectFieldId
    const fieldName = `field_${singleSelectFieldId}`

    // First, we virtually need to figure out if the row was in the old stack.
    const oldRow = populateRow(clone(row))
    const oldRowMatchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row: oldRow,
      fields,
    })
    const oldOption = oldRow[fieldName]
    const oldStackId = oldOption !== null ? oldOption.id : 'null'
    const oldStackResults = clone(getters.getStack(oldStackId).results)
    const oldExistingIndex = oldStackResults.findIndex(
      (r) => r.id === oldRow.id
    )
    const oldExists = oldExistingIndex > -1 && oldRowMatchesFilters

    // Second, we need to figure out if the row should be visible in the new stack.
    const newRow = Object.assign(populateRow(clone(row)), values)
    const newRowMatchesFilters = await dispatch('rowMatchesFilters', {
      view,
      row: newRow,
      fields,
    })
    const newOption = newRow[fieldName]
    const newStackId = newOption !== null ? newOption.id : 'null'
    const newStack = getters.getStack(newStackId)
    const newStackResults = clone(newStack.results)
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
    newStackResults.sort(getRowSortFunction(this.$registry, [], fields))
    const newIndex = newStackResults.findIndex((r) => r.id === newRow.id)
    const newIsLast = newIndex === newStackResults.length - 1
    const newExists =
      (!newIsLast || newStackResults.length === newStackCount) &&
      newRowMatchesFilters

    commit('UPDATE_ROW', { row, values })

    if (oldExists && newExists) {
      commit('MOVE_ROW', {
        currentStackId: oldStackId,
        currentIndex: oldExistingIndex,
        targetStackId: newStackId,
        targetIndex: newIndex,
      })
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
   * Used when row data needs to be directly re-fetched from the Backend and
   * the other (background) row needs to be refreshed. For example, when editing
   * row from a *different* table using ForeignRowEditModal or just RowEditModal
   * component in general.
   */
  async refreshRowFromBackend(
    { commit, getters, rootGetters },
    { table, row }
  ) {
    const gridId = getters.getLastKanbanId
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
   * The dragging of rows to other stacks and position basically consists of three+
   * steps. First is calling this action which brings the rows into dragging state
   * and stores what the current stack and and index was. A row in dragging state is
   * basically an invisible placeholder card that can be moved to other positions
   * using the available actions. When the row has been dragged to the right
   * position, the `stopRowDrag` action can be called to finalize it.
   */
  startRowDrag({ commit, getters }, { row }) {
    const current = getters.findStackIdAndIndex(row.id)
    const currentStackId = current[0]
    const currentIndex = current[1]
    const rows = getters.getStack(currentStackId).results
    const currentBefore = rows[currentIndex + 1] || null

    commit('START_ROW_DRAG', {
      row,
      currentStackId,
      currentBefore,
    })
  },
  /**
   * This action removes the dragging state of a row, will figure out which values
   * need to updated and will make a call to the backend. If something goes wrong,
   * the row is moved back to the original stack and position.
   */
  async stopRowDrag({ dispatch, commit, getters }, { table, fields }) {
    const row = getters.getDraggingRow

    if (row === null) {
      return
    }

    // First we need to figure out what the current position of the row is and how
    // that should be communicated to the backend later. The backend expects another
    // row id where it is placed before or null if it's placed in the end.
    const originalStackId = getters.getDraggingOriginalStackId
    const originalBefore = getters.getDraggingOriginalBefore
    const current = getters.findStackIdAndIndex(row.id)
    const currentStackId = current[0]
    const currentIndex = current[1]
    const rows = getters.getStack(currentStackId).results
    const before = rows[currentIndex + 1] || null

    // We need to have the single select option field instance because we need
    // access to the available options. We can figure that out by looking looping
    // over the provided fields.
    const singleSelectField = fields.find(
      (field) => field.id === getters.getSingleSelectFieldId
    )
    const singleSelectFieldType = this.$registry.get(
      'field',
      SingleSelectFieldType.getType()
    )

    // We immediately want to update the single select value in the row, so we need
    // to extract the correct old value and the new value from the single select field
    // because that object holds all the options.
    const singleSelectFieldName = `field_${getters.getSingleSelectFieldId}`
    const oldSingleSelectFieldValue = row[singleSelectFieldName]
    const newSingleSelectFieldValue =
      singleSelectField.select_options.find(
        (option) => option.id === parseInt(currentStackId)
      ) || null

    // Prepare the objects that are needed to update the row directly in the store.
    const newValues = {}
    const oldValues = {}
    newValues[singleSelectFieldName] = newSingleSelectFieldValue
    oldValues[singleSelectFieldName] = oldSingleSelectFieldValue

    // Because the backend might accept a different format, we need to prepare the
    // values that we're going to send.
    const newValuesForUpdate = {}
    newValuesForUpdate[singleSelectFieldName] =
      singleSelectFieldType.prepareValueForUpdate(
        singleSelectField,
        newSingleSelectFieldValue
      )

    // Immediately update the row in the store and stop the dragging state.
    commit('UPDATE_ROW', { row, values: newValues })
    commit('STOP_ROW_DRAG', { row })

    // If the stack has changed, the value needs to be updated with the backend.
    if (originalStackId !== currentStackId) {
      try {
        const { data } = await RowService(this.$client).update(
          table.id,
          row.id,
          newValuesForUpdate,
          getters.getLastKanbanId
        )
        commit('UPDATE_ROW', { row, values: data })
      } catch (error) {
        // If for whatever reason updating the value fails, we need to undo the
        // things that have changed in the store.
        commit('UPDATE_ROW', { row, values: oldValues })
        dispatch('cancelRowDrag', { row, originalStackId })
        throw error
      }
    }

    // If the row is not before the same or if the stack has changed, we must update
    // the position.
    if (
      (before || { id: null }).id !== (originalBefore || { id: null }).id ||
      originalStackId !== currentStackId
    ) {
      try {
        const { data } = await RowService(this.$client).move(
          table.id,
          row.id,
          before !== null ? before.id : null
        )
        commit('UPDATE_ROW', { row, values: data })
      } catch (error) {
        dispatch('cancelRowDrag', { row, originalStackId })
        throw error
      }
    }
  },
  /**
   * Cancels the current row drag action by reverting back to the original position
   * while respecting any new rows that have been moved into there in the mean time.
   */
  cancelRowDrag({ dispatch, getters, commit }, { row, originalStackId }) {
    const current = getters.findStackIdAndIndex(row.id)

    if (current !== undefined) {
      const currentStackId = current[0]

      const sortedRows = clone(getters.getStack(originalStackId).results)
      if (currentStackId !== originalStackId) {
        // Only add the row to the temporary copy if it doesn't live the current stack.
        sortedRows.push(row)
      }
      sortedRows.sort(getRowSortFunction(this.$registry, [], [], null))
      const targetIndex = sortedRows.findIndex((r) => r.id === row.id)

      dispatch('forceMoveRowTo', {
        row,
        targetStackId: originalStackId,
        targetIndex,
      })
      commit('STOP_ROW_DRAG', { row })
    }
  },
  /**
   * Moves the provided row to the target stack at the provided index.
   *
   * @param row
   * @param targetStackId
   * @param targetIndex
   */
  forceMoveRowTo({ commit, getters }, { row, targetStackId, targetIndex }) {
    const current = getters.findStackIdAndIndex(row.id)

    if (current !== undefined) {
      const currentStackId = current[0]
      const currentIndex = current[1]

      if (currentStackId !== targetStackId || currentIndex !== targetIndex) {
        commit('MOVE_ROW', {
          currentStackId,
          currentIndex,
          targetStackId,
          targetIndex,
        })
        return true
      }
    }
    return false
  },
  /**
   * Moves the provided existing row before or after the provided target row.
   *
   * @param row           The row object that must be moved.
   * @param targetRow     Will be placed before or after the provided row.
   * @param targetBefore  Indicates whether the row must be moved before or after
   *                      the target row.
   */
  forceMoveRowBefore({ dispatch, getters }, { row, targetRow, targetBefore }) {
    const target = getters.findStackIdAndIndex(targetRow.id)

    if (target !== undefined) {
      const targetStackId = target[0]
      const targetIndex = target[1] + (targetBefore ? 0 : 1)

      return dispatch('forceMoveRowTo', { row, targetStackId, targetIndex })
    }
    return false
  },
  /**
   * Updates the value of a row and make the changes to the store accordingly.
   */
  async updateRowValue(
    { commit, dispatch, getters },
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
          getters.getLastKanbanId
        )
        const updatedFieldIds = data.metadata?.updated_field_ids || []

        const readOnlyData = extractChangedFields(
          data.items[0],
          fields,
          updatedFieldIds,
          this.$registry
        )
        commit('UPDATE_ROW', { row, values: readOnlyData })
      }, row.id)
    } catch (error) {
      dispatch('updatedExistingRow', {
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
   * Creates a new stack by updating the related field option of the view's
   * field. The values in the store also be updated accordingly.
   */
  async createStack({ getters, commit, dispatch }, { fields, color, value }) {
    const field = fields.find(
      (field) => field.id === getters.getSingleSelectFieldId
    )

    const updateValues = {
      type: field.type,
      select_options: clone(field.select_options),
    }
    updateValues.select_options.push({ color, value })

    // Instead of using the field store, we manually update the existing field
    // because we need to extract the newly created select option id from the
    // response before the field is updated in the store.
    const { data } = await FieldService(this.$client).update(
      field.id,
      updateValues
    )

    // Extract the newly created select option id from the response and create an
    // empty stack with that id. The stack must exist before the field is updated
    // in the store, otherwise we could ran into vue errors because the stack is
    // expected.
    const selectOptionId =
      data.select_options[data.select_options.length - 1].id.toString()
    const stackObject = populateStack({
      count: 0,
      results: [],
    })
    commit('ADD_STACK', { id: selectOptionId, stack: stackObject })

    // After the stack has been created, we can update the field in the store.
    await dispatch(
      'field/forceUpdate',
      {
        field,
        oldField: clone(field),
        data,
        relatedFields: data.related_fields,
      },
      { root: true }
    )
  },
  /**
   * Updates the stack by updating the related field option of the view's field. The
   * values in the store also be updated accordingly.
   */
  async updateStack(
    { getters, commit, dispatch },
    { fields, optionId, values }
  ) {
    const field = fields.find(
      (field) => field.id === getters.getSingleSelectFieldId
    )

    const options = clone(field.select_options)
    const index = options.findIndex((o) => o.id === optionId)
    Object.assign(options[index], values)

    const updateValues = {
      type: field.type,
      select_options: options,
    }
    const { data } = await FieldService(this.$client).update(
      field.id,
      updateValues
    )

    commit('UPDATE_VALUE_OF_ALL_ROWS_IN_STACK', {
      fieldId: field.id,
      stackId: optionId.toString(),
      values,
    })

    // After the stack has been updated, we can update the field in the store.
    await dispatch(
      'field/forceUpdate',
      {
        field,
        oldField: clone(field),
        data,
        relatedFields: data.related_fields,
      },
      { root: true }
    )
  },
  /**
   * Deletes an existing by updating the related field option of the view's single
   * select field.
   */
  async deleteStack(
    { getters, commit, dispatch },
    { singleSelectField, optionId, deferredFieldUpdate = false }
  ) {
    const options = clone(singleSelectField.select_options)
    const index = options.findIndex((o) => o.id === optionId)
    options.splice(index, 1)

    const updateValues = {
      type: singleSelectField.type,
      select_options: options,
    }
    const { data } = await FieldService(this.$client).update(
      singleSelectField.id,
      updateValues
    )

    const doFieldUpdate = async () => {
      // After the stack has been updated, we can update the field in the store.
      await dispatch(
        'field/forceUpdate',
        {
          singleSelectField,
          oldField: clone(singleSelectField),
          data,
          relatedFields: data.related_fields,
        },
        { root: true }
      )
    }

    return deferredFieldUpdate ? doFieldUpdate : doFieldUpdate()
  },
  /**
   * Adds a field with a provided value to the rows in the store. This will for
   * example be called when a new field has been created.
   */
  addField({ commit }, { field, value = null }) {
    commit('ADD_FIELD_TO_ALL_ROWS', { field, value })
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
  getLastKanbanId(state) {
    return state.lastKanbanId
  },
  getSingleSelectFieldId(state) {
    return state.singleSelectFieldId
  },
  getAllFieldOptions(state) {
    return state.fieldOptions
  },
  getAllStacks: (state) => {
    return state.stacks
  },
  getStack: (state) => (id) => {
    return state.stacks[id.toString()]
  },
  stackExists: (state) => (id) => {
    return Object.prototype.hasOwnProperty.call(state.stacks, id.toString())
  },
  getBufferRequestSize(state) {
    return state.bufferRequestSize
  },
  isDraggingRow(state) {
    return !!state.draggingRow
  },
  getDraggingRow(state) {
    return state.draggingRow
  },
  getDraggingOriginalStackId(state) {
    return state.draggingOriginalStackId
  },
  getDraggingOriginalBefore(state) {
    return state.draggingOriginalBefore
  },
  getAllRows(state) {
    let rows = []
    Object.keys(state.stacks).forEach((key) => {
      rows = rows.concat(state.stacks[key].results)
    })
    return rows
  },
  findStackIdAndIndex: (state) => (rowId) => {
    const stacks = state.stacks
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
