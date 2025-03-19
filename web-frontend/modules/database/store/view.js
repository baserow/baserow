import { v1 as uuidv1 } from 'uuid'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { uuid } from '@baserow/modules/core/utils/string'
import {
  createFiltersTree,
  readDefaultViewIdFromCookie,
  saveDefaultViewIdInCookie,
} from '@baserow/modules/database/utils/view'
import ViewService from '@baserow/modules/database/services/view'
import FilterService from '@baserow/modules/database/services/filter'
import DecorationService from '@baserow/modules/database/services/decoration'
import SortService from '@baserow/modules/database/services/sort'
import GroupByService from '@baserow/modules/database/services/groupBy'
import { clone } from '@baserow/modules/core/utils/object'
import { DATABASE_ACTION_SCOPES } from '@baserow/modules/database/utils/undoRedoConstants'
import { createNewUndoRedoActionGroupId } from '@baserow/modules/database/utils/action'

export function populateFilter(filter) {
  filter._ = {
    hover: false,
    loading: false,
  }
  return filter
}

export function populateFilterGroup(filterGroup) {
  filterGroup._ = {
    hover: false,
    loading: false,
  }
  return filterGroup
}

export function populateSort(sort) {
  sort._ = {
    hover: false,
    loading: false,
  }
  return sort
}

export function populateGroupBy(groupBy) {
  groupBy._ = {
    hover: false,
    loading: false,
    width: null,
  }
  return groupBy
}

export function populateDecoration(decoration) {
  decoration._ = { loading: false }
  return decoration
}

export function populateView(view, registry) {
  const type = registry.get('view', view.type)

  view._ = view._ || {
    type: type.serialize(),
    selected: false,
    loading: false,
    focusFilter: null,
  }

  view.isShared = type.isShared(view)

  if (Object.prototype.hasOwnProperty.call(view, 'filters')) {
    view.filters.forEach((filter) => {
      populateFilter(filter)
    })
  } else {
    view.filters = []
  }

  if (Object.prototype.hasOwnProperty.call(view, 'filter_groups')) {
    view.filter_groups.forEach((filterGroup) => {
      populateFilterGroup(filterGroup)
    })
  } else {
    view.filter_groups = []
  }

  if (Object.prototype.hasOwnProperty.call(view, 'sortings')) {
    view.sortings.forEach((sort) => {
      populateSort(sort)
    })
  } else {
    view.sortings = []
  }
  if (Object.prototype.hasOwnProperty.call(view, 'group_bys')) {
    view.group_bys.forEach((groupBy) => {
      populateGroupBy(groupBy)
    })
  } else {
    view.group_bys = []
  }

  if (Object.prototype.hasOwnProperty.call(view, 'group_bys')) {
    view.group_bys.forEach((groupBy) => {
      populateGroupBy(groupBy)
    })
  } else {
    view.group_bys = []
  }

  if (Object.prototype.hasOwnProperty.call(view, 'decorations')) {
    view.decorations.forEach((decoration) => {
      populateDecoration(decoration)
    })
  } else {
    view.decorations = []
  }

  return type.populate(view)
}

export const state = () => ({
  types: {},
  loading: false,
  items: [],
  selected: {},
  defaultViewId: null,
})

export const mutations = {
  SET_ITEMS(state, applications) {
    state.items = applications
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_ITEM_LOADING(state, { view, value }) {
    if (!Object.prototype.hasOwnProperty.call(view, '_')) {
      return
    }
    view._.loading = value
  },
  ADD_ITEM(state, item) {
    if (!state.items.some((existingItem) => existingItem.id === item.id))
      state.items = [...state.items, item].sort((a, b) => a.order - b.order)
  },
  UPDATE_ITEM(state, { id, view, values, repopulate, readOnly }) {
    if (!readOnly) {
      const index = state.items.findIndex((item) => item.id === id)
      Object.assign(state.items[index], state.items[index], values)
      if (repopulate === true) {
        populateView(state.items[index], this.$registry)
      }
    } else {
      Object.assign(view, view, values)
    }
  },
  ORDER_ITEMS(state, { ownershipType, order }) {
    if (ownershipType === undefined) {
      const firstView = state.items.find((item) => item.id === order[0])
      ownershipType = firstView.ownership_type
    }
    const items = state.items.filter(
      (view) => view.ownership_type === ownershipType
    )
    items.forEach((view) => {
      const index = order.findIndex((value) => value === view.id)
      view.order = index === -1 ? 0 : index + 1
    })
  },
  DELETE_ITEM(state, id) {
    const index = state.items.findIndex((item) => item.id === id)
    state.items.splice(index, 1)
  },
  SET_SELECTED(state, view) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    view._.selected = true
    state.selected = view
  },
  UNSELECT(state) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    state.selected = {}
  },
  ADD_FILTER(state, { view, filter }) {
    filter.view = view.id
    view.filters.push(filter)
  },
  FINALIZE_FILTER(state, { view, oldId, id }) {
    const index = view.filters.findIndex((item) => item.id === oldId)
    if (index !== -1) {
      view.filters[index].id = id
      view.filters[index]._.loading = false
    }
  },
  SET_FILTER_FOCUS(state, { view, filterId }) {
    view._.focusFilter = filterId
  },
  DELETE_FILTER(state, { view, id }) {
    const index = view.filters.findIndex((item) => item.id === id)
    if (index !== -1) {
      view.filters.splice(index, 1)
    }
  },
  ADD_FILTER_GROUP(state, { view, filterGroup }) {
    filterGroup.view = view.id
    view.filter_groups.push(filterGroup)
  },
  FINALIZE_FILTER_GROUP(state, { view, oldId, id }) {
    const index = view.filter_groups.findIndex((item) => item.id === oldId)
    if (index !== -1) {
      view.filter_groups[index].id = id
      view.filter_groups[index]._.loading = false
    }
  },
  UPDATE_FILTER_GROUP(state, { filterGroup, values }) {
    Object.assign(filterGroup, filterGroup, values)
  },
  DELETE_FILTER_GROUP(state, { view, id }) {
    const index = view.filter_groups.findIndex((item) => item.id === id)
    if (index !== -1) {
      view.filter_groups.splice(index, 1)
    }
  },
  DELETE_FIELD_FILTERS(state, { view, fieldId }) {
    for (let i = view.filters.length - 1; i >= 0; i--) {
      if (view.filters[i].field === fieldId) {
        view.filters.splice(i, 1)
      }
    }
  },
  UPDATE_FILTER(state, { filter, values }) {
    Object.assign(filter, filter, values)
  },
  SET_FILTER_LOADING(state, { filter, value }) {
    filter._.loading = value
  },
  ADD_DECORATION(state, { view, decoration }) {
    view.decorations.push({
      type: null,
      value_provider_type: null,
      value_provider_conf: null,
      ...decoration,
    })
  },
  FINALIZE_DECORATION(state, { view, oldId, id }) {
    const index = view.decorations.findIndex((item) => item.id === oldId)
    if (index !== -1) {
      view.decorations[index].id = id
      view.decorations[index]._.loading = false
    }
  },
  DELETE_DECORATION(state, { view, id }) {
    const index = view.decorations.findIndex((item) => item.id === id)
    if (index !== -1) {
      view.decorations.splice(index, 1)
    }
  },
  UPDATE_DECORATION(state, { decoration, values }) {
    Object.assign(decoration, decoration, values)
  },
  SET_DECORATION_LOADING(state, { decoration, value }) {
    decoration._.loading = value
  },
  ADD_SORT(state, { view, sort }) {
    view.sortings.push(sort)
  },
  FINALIZE_SORT(state, { view, oldId, id }) {
    const index = view.sortings.findIndex((item) => item.id === oldId)
    if (index !== -1) {
      view.sortings[index].id = id
      view.sortings[index]._.loading = false
    }
  },
  DELETE_SORT(state, { view, id }) {
    const index = view.sortings.findIndex((item) => item.id === id)
    if (index !== -1) {
      view.sortings.splice(index, 1)
    }
  },
  DELETE_FIELD_SORTINGS(state, { view, fieldId }) {
    for (let i = view.sortings.length - 1; i >= 0; i--) {
      if (view.sortings[i].field === fieldId) {
        view.sortings.splice(i, 1)
      }
    }
  },
  UPDATE_SORT(state, { sort, values }) {
    Object.assign(sort, sort, values)
  },
  SET_SORT_LOADING(state, { sort, value }) {
    sort._.loading = value
  },
  ADD_GROUP_BY(state, { view, groupBy }) {
    view.group_bys.push(groupBy)
  },
  FINALIZE_GROUP_BY(state, { view, oldId, id }) {
    const index = view.group_bys.findIndex((item) => item.id === oldId)
    if (index !== -1) {
      view.group_bys[index].id = id
      view.group_bys[index]._.loading = false
    }
  },
  DELETE_GROUP_BY(state, { view, id }) {
    const index = view.group_bys.findIndex((item) => item.id === id)
    if (index !== -1) {
      view.group_bys.splice(index, 1)
    }
  },
  DELETE_FIELD_GROUP_BYS(state, { view, fieldId }) {
    for (let i = view.group_bys.length - 1; i >= 0; i--) {
      if (view.group_bys[i].field === fieldId) {
        view.group_bys.splice(i, 1)
      }
    }
  },
  UPDATE_GROUP_BY(state, { groupBy, values }) {
    Object.assign(groupBy, groupBy, values)
  },
  SET_GROUP_BY_LOADING(state, { groupBy, value }) {
    groupBy._.loading = value
  },
  /**
   * Data for defaultViewId for Vuex store:
   * {
   *   defaultViewId: view1Id,
   * }
   */
  SET_DEFAULT_VIEW_ID(state, viewId) {
    state.defaultViewId = viewId
  },
}

export const actions = {
  /**
   * Changes the loading state of a specific view.
   */
  setItemLoading({ commit }, { view, value }) {
    commit('SET_ITEM_LOADING', { view, value })
  },
  /**
   * Fetches all the views of a given table. The is mostly called when the user
   * selects a different table.
   */
  async fetchAll({ commit, getters, dispatch, state }, table) {
    commit('SET_LOADING', true)
    commit('UNSELECT', {})

    try {
      const { data } = await ViewService(this.$client).fetchAll(
        table.id,
        true,
        true,
        true,
        true
      )
      data.forEach((part, index, d) => {
        populateView(data[index], this.$registry)
      })
      commit('SET_ITEMS', data)
      commit('SET_LOADING', false)

      // Get the default view for the table.
      const defaultViewId = readDefaultViewIdFromCookie(this.$cookies, table.id)
      if (defaultViewId !== null) {
        commit('SET_DEFAULT_VIEW_ID', defaultViewId)
      }
    } catch (error) {
      commit('SET_ITEMS', [])
      commit('SET_LOADING', false)

      throw error
    }
  },
  /**
   * Creates a new view with the provided type for the given table.
   */
  async create(
    { commit, getters, rootGetters, dispatch },
    { type, table, values }
  ) {
    if (Object.prototype.hasOwnProperty.call(values, 'type')) {
      throw new Error(
        'The key "type" is a reserved, but is already set on the ' +
          'values when creating a new view.'
      )
    }

    if (!this.$registry.exists('view', type)) {
      throw new Error(`A view with type "${type}" doesn't exist.`)
    }

    const postData = clone(values)
    postData.type = type

    const { data } = await ViewService(this.$client).create(table.id, postData)
    return await dispatch('forceCreate', { data })
  },
  /**
   * Forcefully create a new view without making a request to the server.
   */
  forceCreate({ commit }, { data }) {
    populateView(data, this.$registry)
    commit('ADD_ITEM', data)
    return { view: data }
  },
  /**
   * Updates the values of the view with the provided id.
   */
  async update(
    { commit, dispatch },
    {
      view,
      values,
      readOnly = false,
      refreshFromFetch = false,
      optimisticUpdate = true,
    }
  ) {
    commit('SET_ITEM_LOADING', { view, value: true })
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(view, name)) {
        oldValues[name] = view[name]
        newValues[name] = values[name]
      }
    })

    function updatePublicViewHasPassword() {
      // public_view_has_password needs to be updated after the api request
      // is finished and the modal closes.
      const viewHasPassword = Object.keys(values).includes(
        'public_view_password'
      )
        ? values.public_view_password !== ''
        : view.public_view_has_password
      // update the password protection toggle state accordingly
      dispatch('forceUpdate', {
        view,
        values: {
          public_view_has_password: viewHasPassword,
        },
      })
    }

    if (optimisticUpdate) {
      dispatch('forceUpdate', {
        view,
        values: newValues,
        repopulate: true,
        readOnly,
      })
    }
    try {
      if (!readOnly) {
        dispatch(
          'undoRedo/updateCurrentScopeSet',
          DATABASE_ACTION_SCOPES.view(view.id),
          {
            root: true,
          }
        )
        // in some cases view may return extra data that were not present in values
        const newValues = (
          await ViewService(this.$client).update(view.id, values)
        ).data
        if (refreshFromFetch || !optimisticUpdate) {
          dispatch('forceUpdate', { view, values: newValues, repopulate: true })
        }

        updatePublicViewHasPassword()
      }
      commit('SET_ITEM_LOADING', { view, value: false })
    } catch (error) {
      commit('SET_ITEM_LOADING', { view, value: false })
      dispatch('forceUpdate', { view, values: oldValues })
      throw error
    }
  },
  /**
   * Updates the order of all the views in a table.
   */
  async order({ commit, getters }, { table, ownershipType, order, oldOrder }) {
    commit('ORDER_ITEMS', { ownershipType, order })

    try {
      await ViewService(this.$client).order(table.id, ownershipType, order)
    } catch (error) {
      commit('ORDER_ITEMS', { ownershipType, order: oldOrder })
      throw error
    }
  },
  /**
   * Forcefully update an existing view without making a request to the backend.
   */
  forceUpdate(
    { commit },
    { view, values, repopulate = false, readOnly = false }
  ) {
    commit('UPDATE_ITEM', {
      id: view.id,
      view,
      values,
      repopulate,
      readOnly,
    })
  },
  /**
   * Duplicates an existing view.
   */
  async duplicate({ commit, dispatch }, view) {
    const { data } = await ViewService(this.$client).duplicate(view.id)
    await dispatch('forceCreate', { data })
    return data
  },
  /**
   * Deletes an existing view with the provided id. A request to the server is first
   * made and after that it will be deleted from the store.
   */
  async delete({ commit, dispatch }, view) {
    try {
      await ViewService(this.$client).delete(view.id)
      dispatch('forceDelete', view)
    } catch (error) {
      // If the view to delete wasn't found we can just delete it from the
      // state.
      if (error.response && error.response.status === 404) {
        dispatch('forceDelete', view)
      } else {
        throw error
      }
    }
  },
  /**
   * Removes the view from the this store without making a delete request to the server.
   */
  forceDelete({ commit, dispatch, getters, rootGetters }, view) {
    // If the currently selected view is selected.
    if (view._.selected && view.id === getters.getSelectedId) {
      commit('UNSELECT')

      const route = this.$router.history.current
      const tableId = view.table.id

      // If the current route is the same table as the deleting view.
      if (
        route.name === 'database-table' &&
        parseInt(route.params.tableId) === tableId
      ) {
        // Check if there are any other views and figure out what the next selected
        // view should be. This is always the first one in the list.
        const otherViews = getters.getAll
          .filter((v) => view.id !== v.id)
          .sort((a, b) => a.order - b.order)
        const nextView = otherViews.length > 0 ? otherViews[0] : null

        if (nextView !== null) {
          // If there is a next view, we can redirect to that page.
          this.$router.replace({ params: { viewId: nextView.id } })
        } else if (route.params.viewId) {
          // If there isn't a next view and the user was already viewing a view, we
          // need to redirect to the empty table page.
          this.$router.replace({ params: { viewId: null } })
        } else {
          // If there isn't a next view and the user wasn't looking at a view, we need
          // to refresh to show an empty table page. Changing the view id to 0,
          // which never exists forces the table page to show empty. We have
          // to do it this way because we can't navigate to the page without view.
          this.$router.replace({ params: { viewId: '0' } })
        }
      }
    }

    commit('DELETE_ITEM', view.id)
  },
  /**
   * Select a view and fetch all the applications related to that view. Note that
   * only the views of the selected table are stored in this store. It might be
   * possible you need to select the table first.
   */
  select({ commit, dispatch }, view) {
    commit('SET_SELECTED', view)
    commit('SET_DEFAULT_VIEW_ID', view.id)

    // Set the default view for the table.
    saveDefaultViewIdInCookie(this.$cookies, view, this.$config)

    dispatch(
      'undoRedo/updateCurrentScopeSet',
      DATABASE_ACTION_SCOPES.view(view.id),
      {
        root: true,
      }
    )
    return { view }
  },
  /**
   * Unselect the currently selected view.
   */
  unselect({ commit, dispatch }) {
    commit('UNSELECT', {})
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      DATABASE_ACTION_SCOPES.view(null),
      {
        root: true,
      }
    )
  },
  /**
   * Selects a view by a given view id. Note that only the views of the selected
   * table are stored in this store. It might be possible you need to select the
   * table first.
   */
  selectById({ dispatch, getters }, id) {
    const view = getters.get(id)
    if (view === undefined) {
      throw new StoreItemLookupError(`View with id ${id} is not found.`)
    }
    return dispatch('select', view)
  },
  /**
   * Changes the loading state of a specific filter.
   */
  setFilterLoading({ commit }, { filter, value }) {
    commit('SET_FILTER_LOADING', { filter, value })
  },
  /**
   * Focus a specific filter.
   */
  setFocusFilter({ commit }, { view, filterId }) {
    commit('SET_FILTER_FOCUS', { view, filterId })
  },
  /**
   * Creates a new filter and adds it to the store right away. If the API call succeeds
   * the filter ID will be added, but if it fails it will be removed from the store.
   * It also create the filter group if it doesn't exist yet in the same optimistic
   * way, removing it if the API call fails.
   */
  async createFilter(
    { commit },
    {
      view,
      field,
      values,
      emitEvent = true,
      readOnly = false,
      filterGroupId = null,
      parentGroupId = null,
    }
  ) {
    // If the type is not provided we are going to choose the first available type.
    if (!Object.prototype.hasOwnProperty.call(values, 'type')) {
      const viewFilterTypes = this.$registry.getAll('viewFilter')
      const compatibleType = Object.values(viewFilterTypes).find(
        (viewFilterType) => {
          return viewFilterType.fieldIsCompatible(field)
        }
      )
      if (compatibleType === undefined) {
        throw new Error(
          `No compatible filter type could be found for field' ${field.type}`
        )
      }
      values.type = compatibleType.type
    }

    // If the value is not provided, then we use the default value related to the type.
    if (!Object.prototype.hasOwnProperty.call(values, 'value')) {
      const viewFilterType = this.$registry.get('viewFilter', values.type)
      values.value = viewFilterType.getDefaultValue(field)
    }

    // Some filter input components expect the preload values to exist, that's why we
    // need to add an empty object if it doesn't yet exist. They can all handle
    // empty preload_values.
    if (!Object.prototype.hasOwnProperty.call(values, 'preload_values')) {
      values.preload_values = {}
    }

    // If the filter group doesn't exist yet optimistically create it.
    // If we first create the filter group and only once that succeeds create the
    // filter itself, we can run into a situation where a user with a slow connection
    // will see an empty group first and the filter only after a while. This code
    // will optimistically create both the group and the filter to provide a smoother
    // experience.
    const createNewFilterGroup =
      filterGroupId &&
      view.filter_groups.findIndex((group) => group.id === filterGroupId) === -1

    const filterGroup = {}
    if (createNewFilterGroup) {
      populateFilterGroup(filterGroup)
      filterGroup.id = filterGroupId
      filterGroup._.loading = !readOnly
      filterGroup.filter_type = 'AND'
      filterGroup.parent_group = parentGroupId
      commit('ADD_FILTER_GROUP', { view, filterGroup })
    }

    const filter = Object.assign({}, values)
    populateFilter(filter)
    filter.id = uuidv1()
    filter._.loading = !readOnly
    filter.group = filterGroupId
    values.group = filterGroupId
    commit('ADD_FILTER', { view, filter })

    if (emitEvent) {
      this.$bus.$emit('view-filter-created', { view, filter })
    }
    commit('SET_FILTER_FOCUS', { view, filterId: filter.id })

    const undoRedoActionGroupId = createNewUndoRedoActionGroupId()
    if (!readOnly) {
      if (createNewFilterGroup) {
        // The group needs to be created first before we can create the filter
        // in the case we're trying to create a new filter in a new group.
        try {
          const { data } = await FilterService(this.$client).createGroup(
            view.id,
            parentGroupId,
            undoRedoActionGroupId
          )
          commit('FINALIZE_FILTER_GROUP', {
            view,
            oldId: filterGroup.id,
            id: data.id,
          })
          // update the group id with the created group id
          values.group = data.id
          commit('UPDATE_FILTER', { filter, values: { group: data.id } })
        } catch (error) {
          commit('DELETE_FILTER_GROUP', { view, id: filterGroup.id })
          commit('DELETE_FILTER', { view, id: filter.id })
          throw error
        }
      }

      try {
        const { data } = await FilterService(this.$client).create(
          view.id,
          values,
          undoRedoActionGroupId
        )
        commit('FINALIZE_FILTER', { view, oldId: filter.id, id: data.id })
      } catch (error) {
        commit('DELETE_FILTER', { view, id: filter.id })
        throw error
      }
    }

    return { filter }
  },
  /**
   * Creates a new filter group and adds it to the store right away. If the API
   * call succeeds the filter group ID will be updated, but if it fails it will be
   * removed from the store.
   */
  async createFilterGroup({ commit }, { view, readOnly = false }) {
    const filterGroup = {}
    populateFilterGroup(filterGroup)
    filterGroup.id = uuidv1()
    filterGroup._.loading = !readOnly
    filterGroup.filter_type = 'AND'

    commit('ADD_FILTER_GROUP', { view, filterGroup })

    try {
      const { data } = await FilterService(this.$client).createGroup(view.id)
      commit('FINALIZE_FILTER_GROUP', {
        view,
        oldId: filterGroup.id,
        id: data.id,
      })
    } catch (error) {
      commit('DELETE_FILTER_GROUP', { view, id: filterGroup.id })
      throw error
    }

    return { filterGroup }
  },
  /**
   * Forcefully create a new view filter group without making a request to the backend.
   */
  forceCreateFilterGroup({ commit }, { view, values }) {
    const filterGroup = Object.assign({}, values)
    populateFilterGroup(filterGroup)
    commit('ADD_FILTER_GROUP', { view, filterGroup })
  },
  /**
   * Forcefully create a new view filter without making a request to the backend.
   */
  forceCreateFilter({ commit }, { view, values }) {
    const filter = Object.assign({}, values) // clone the object
    populateFilter(filter)
    commit('ADD_FILTER', { view, filter })
  },
  /**
   * Updates the filter values in the store right away. If the API call fails the
   * changes will be undone.
   */
  async updateFilter(
    { dispatch, commit },
    { filter, values, readOnly = false }
  ) {
    commit('SET_FILTER_LOADING', { filter, value: true })

    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(filter, name)) {
        oldValues[name] = filter[name]
        newValues[name] = values[name]
      }
    })

    // When updating a filter, the preload values must be cleared because they
    // might not match the filter anymore.
    newValues.preload_values = {}

    dispatch('forceUpdateFilter', { filter, values: newValues })

    try {
      if (!readOnly) {
        await FilterService(this.$client).update(filter.id, values)
      }
      commit('SET_FILTER_LOADING', { filter, value: false })
    } catch (error) {
      dispatch('forceUpdateFilter', { filter, values: oldValues })
      commit('SET_FILTER_LOADING', { filter, value: false })
      throw error
    }
  },
  /**
   *
   */
  async updateFilterGroup(
    { dispatch },
    { filterGroup, values, readOnly = false }
  ) {
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(filterGroup, name)) {
        oldValues[name] = filterGroup[name]
        newValues[name] = values[name]
      }
    })

    dispatch('forceUpdateFilterGroup', {
      filterGroup,
      values: newValues,
    })

    try {
      if (!readOnly) {
        await FilterService(this.$client).updateGroup(filterGroup.id, values)
      }
    } catch (error) {
      dispatch('forceUpdateFilterGroup', {
        filterGroup,
        values: oldValues,
      })
      throw error
    }
  },
  /**
   * Forcefully update an existing view filter group without making a request to the backend.
   */
  forceUpdateFilterGroup({ commit }, { filterGroup, values }) {
    commit('UPDATE_FILTER_GROUP', { filterGroup, values })
  },
  /**
   * Forcefully update an existing view filter without making a request to the backend.
   */
  forceUpdateFilter({ commit }, { filter, values }) {
    commit('UPDATE_FILTER', { filter, values })
  },
  /**
   * Deletes an existing filter. A request to the server will be made first and
   * after that it will be deleted.
   */
  async deleteFilter({ dispatch, commit }, { view, filter, readOnly = false }) {
    commit('SET_FILTER_LOADING', { filter, value: true })

    try {
      if (!readOnly) {
        await FilterService(this.$client).delete(filter.id)
      }
      dispatch('forceDeleteFilter', { view, filter })
    } catch (error) {
      commit('SET_FILTER_LOADING', { filter, value: false })
      throw error
    }
  },
  /**
   * Forcefully delete an existing filter without making a request to the backend.
   */
  forceDeleteFilter({ commit }, { view, filter }) {
    commit('DELETE_FILTER', { view, id: filter.id })
  },
  /**
   * Deletes an existing filter. A request to the server will be made first and
   * after that it will be deleted.
   */
  async deleteFilterGroup(
    { dispatch, commit },
    { view, filterGroup, readOnly = false }
  ) {
    const filters = view.filters.filter((f) => f.group === filterGroup.id)
    for (const filter of filters) {
      commit('SET_FILTER_LOADING', { filter, value: true })
    }

    try {
      if (!readOnly) {
        await FilterService(this.$client).deleteGroup(filterGroup.id)
      }
      dispatch('forceDeleteFilterGroup', {
        view,
        filterGroup,
      })
    } catch (error) {
      for (const filter of filters) {
        commit('SET_FILTER_LOADING', { filter, value: false })
      }
      throw error
    }
  },
  /**
   * Forcefully delete an existing filter group without making a request to the backend.
   * This function will also delete all the filters that are part of the group and all
   * the child groups and filters.
   */
  forceDeleteFilterGroup({ commit }, { view, filterGroup }) {
    const filtersTree = createFiltersTree(
      view.filter_type,
      view.filters,
      view.filter_groups
    )
    const groupNode = filtersTree.findNodeByGroupId(filterGroup.id)
    if (groupNode === null) {
      return
    }
    const deleteFromNode = (node) => {
      for (const child in node.children) {
        deleteFromNode(node.children[child])
      }
      for (const filter of node.filters) {
        commit('DELETE_FILTER', { view, id: filter.id })
      }
      commit('DELETE_FILTER_GROUP', { view, id: node.groupId })
    }

    deleteFromNode(groupNode)
  },
  /**
   * When a field is deleted the related filters are also automatically deleted in the
   * backend so they need to be removed here.
   */
  deleteFieldFilters({ commit, getters }, { field }) {
    getters.getAll.forEach((view) => {
      commit('DELETE_FIELD_FILTERS', { view, fieldId: field.id })
    })
  },

  /**
   * Creates a new decoration and adds it to the store right away. If the API call succeeds
   * the decorator ID will be updatede, but if it fails it will be removed from the store.
   */
  async createDecoration({ commit }, { view, values, readOnly = false }) {
    const decoration = { ...values }
    populateDecoration(decoration)
    decoration.id = uuid()
    decoration._.loading = !readOnly

    commit('ADD_DECORATION', { view, decoration })

    try {
      if (!readOnly) {
        const { data } = await DecorationService(this.$client).create(
          view.id,
          values
        )
        commit('FINALIZE_DECORATION', {
          view,
          oldId: decoration.id,
          id: data.id,
        })
      }
    } catch (error) {
      commit('DELETE_DECORATION', { view, id: decoration.id })
      throw error
    }

    return { decoration }
  },
  /**
   * Forcefully create a new view decoration without making a request to the backend.
   */
  forceCreateDecoration({ commit }, { view, values }) {
    const decoration = { ...values }
    populateDecoration(decoration)
    commit('ADD_DECORATION', { view, decoration })
  },
  /**
   * Updates the decoration values in the store right away. If the API call fails the
   * changes will be undone.
   */
  async updateDecoration(
    { dispatch, commit },
    { decoration, values, readOnly = false }
  ) {
    commit('SET_DECORATION_LOADING', { decoration, value: true })

    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(decoration, name)) {
        oldValues[name] = decoration[name]
        newValues[name] = values[name]
      }
    })

    dispatch('forceUpdateDecoration', { decoration, values: newValues })

    try {
      if (!readOnly) {
        await DecorationService(this.$client).update(decoration.id, values)
      }
      commit('SET_DECORATION_LOADING', { decoration, value: false })
    } catch (error) {
      dispatch('forceUpdateDecoration', { decoration, values: oldValues })
      commit('SET_DECORATION_LOADING', { decoration, value: false })
      throw error
    }
  },
  /**
   * Forcefully update an existing view decoration without making a request to the
   * backend.
   */
  forceUpdateDecoration({ commit }, { decoration, values }) {
    commit('UPDATE_DECORATION', { decoration, values })
  },
  /**
   * Deletes an existing decoration. A request to the server will be made first and
   * after that it will be deleted.
   */
  async deleteDecoration(
    { dispatch, commit },
    { view, decoration, readOnly = false }
  ) {
    commit('SET_DECORATION_LOADING', { decoration, value: true })
    dispatch('forceDeleteDecoration', { view, decoration })

    try {
      if (!readOnly) {
        await DecorationService(this.$client).delete(decoration.id)
      }
    } catch (error) {
      // Restore decoration in case of error
      dispatch('forceCreateDecoration', {
        view,
        values: decoration,
      })
      commit('SET_DECORATION_LOADING', { decoration, value: false })
      throw error
    }
  },
  /**
   * Forcefully delete an existing decoration without making a request to the backend.
   */
  forceDeleteDecoration({ commit }, { view, decoration }) {
    commit('DELETE_DECORATION', { view, id: decoration.id })
  },
  /**
   * Changes the loading state of a specific sort.
   */
  setSortLoading({ commit }, { sort, value }) {
    commit('SET_SORT_LOADING', { sort, value })
  },
  /**
   * Creates a new sort and adds it to the store right away. If the API call succeeds
   * the row ID will be added, but if it fails it will be removed from the store.
   */
  async createSort({ getters, commit }, { view, values, readOnly = false }) {
    // If the order is not provided we are going to choose the ascending order.
    if (!Object.prototype.hasOwnProperty.call(values, 'order')) {
      values.order = 'ASC'
    }

    const sort = Object.assign({}, values)
    populateSort(sort)
    sort.id = uuid()
    sort._.loading = !readOnly

    commit('ADD_SORT', { view, sort })

    if (!readOnly) {
      try {
        const { data } = await SortService(this.$client).create(view.id, values)
        commit('FINALIZE_SORT', { view, oldId: sort.id, id: data.id })
      } catch (error) {
        commit('DELETE_SORT', { view, id: sort.id })
        throw error
      }
    }

    return { sort }
  },
  /**
   * Forcefully create a new  view sorting without making a request to the backend.
   */
  forceCreateSort({ commit }, { view, values }) {
    const sort = Object.assign({}, values)
    populateSort(sort)
    commit('ADD_SORT', { view, sort })
  },
  /**
   * Updates the sort values in the store right away. If the API call fails the
   * changes will be undone.
   */
  async updateSort({ dispatch, commit }, { sort, values, readOnly = false }) {
    commit('SET_SORT_LOADING', { sort, value: true })

    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(sort, name)) {
        oldValues[name] = sort[name]
        newValues[name] = values[name]
      }
    })

    dispatch('forceUpdateSort', { sort, values: newValues })

    try {
      if (!readOnly) {
        await SortService(this.$client).update(sort.id, values)
      }
      commit('SET_SORT_LOADING', { sort, value: false })
    } catch (error) {
      dispatch('forceUpdateSort', { sort, values: oldValues })
      commit('SET_SORT_LOADING', { sort, value: false })
      throw error
    }
  },
  /**
   * Forcefully update an existing view sort without making a request to the backend.
   */
  forceUpdateSort({ commit }, { sort, values }) {
    commit('UPDATE_SORT', { sort, values })
  },
  /**
   * Deletes an existing sort. A request to the server will be made first and
   * after that it will be deleted.
   */
  async deleteSort({ dispatch, commit }, { view, sort, readOnly = false }) {
    commit('SET_SORT_LOADING', { sort, value: true })

    try {
      if (!readOnly) {
        await SortService(this.$client).delete(sort.id)
      }
      dispatch('forceDeleteSort', { view, sort })
    } catch (error) {
      commit('SET_SORT_LOADING', { sort, value: false })
      throw error
    }
  },
  /**
   * Forcefully delete an existing view sort without making a request to the backend.
   */
  forceDeleteSort({ commit }, { view, sort }) {
    commit('DELETE_SORT', { view, id: sort.id })
  },
  /**
   * When a field is deleted the related sortings are also automatically deleted in the
   * backend so they need to be removed here.
   */
  deleteFieldSortings({ commit, getters }, { field }) {
    getters.getAll.forEach((view) => {
      commit('DELETE_FIELD_SORTINGS', { view, fieldId: field.id })
    })
  },
  /**
   * Changes the loading state of a specific groupBy.
   */
  setGroupByLoading({ commit }, { groupBy, value }) {
    commit('SET_GROUP_BY_LOADING', { groupBy, value })
  },
  /**
   * Creates a new groupBy and adds it to the store right away. If the API call succeeds
   * the row ID will be added, but if it fails it will be removed from the store.
   */
  async createGroupBy({ getters, commit }, { view, values, readOnly = false }) {
    // If the order is not provided we are going to choose the ascending order.
    if (!Object.prototype.hasOwnProperty.call(values, 'order')) {
      values.order = 'ASC'
    }

    if (!Object.prototype.hasOwnProperty.call(values, 'width')) {
      values.width = 200
    }

    const groupBy = Object.assign({}, values)
    populateGroupBy(groupBy)
    groupBy.id = uuid()
    groupBy._.loading = !readOnly

    commit('ADD_GROUP_BY', { view, groupBy })

    if (!readOnly) {
      try {
        const { data } = await GroupByService(this.$client).create(
          view.id,
          values
        )
        commit('FINALIZE_GROUP_BY', { view, oldId: groupBy.id, id: data.id })
      } catch (error) {
        commit('DELETE_GROUP_BY', { view, id: groupBy.id })
        throw error
      }
    }

    return { groupBy }
  },
  /**
   * Forcefully create a new  view group by without making a request to the backend.
   */
  forceCreateGroupBy({ commit }, { view, values }) {
    const groupBy = Object.assign({}, values)
    populateGroupBy(groupBy)
    commit('ADD_GROUP_BY', { view, groupBy })
  },
  /**
   * Updates the groupBy values in the store right away. If the API call fails the
   * changes will be undone.
   */
  async updateGroupBy(
    { dispatch, commit },
    { groupBy, values, readOnly = false }
  ) {
    commit('SET_GROUP_BY_LOADING', { groupBy, value: true })

    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(groupBy, name)) {
        oldValues[name] = groupBy[name]
        newValues[name] = values[name]
      }
    })

    dispatch('forceUpdateGroupBy', { groupBy, values: newValues })

    try {
      if (!readOnly) {
        await GroupByService(this.$client).update(groupBy.id, values)
      }
      commit('SET_GROUP_BY_LOADING', { groupBy, value: false })
    } catch (error) {
      dispatch('forceUpdateGroupBy', { groupBy, values: oldValues })
      commit('SET_GROUP_BY_LOADING', { groupBy, value: false })
      throw error
    }
  },
  /**
   * Forcefully update an existing view groupBy without making a request to the backend.
   */
  forceUpdateGroupBy({ commit }, { groupBy, values }) {
    commit('UPDATE_GROUP_BY', { groupBy, values })
  },
  /**
   * Deletes an existing groupBy. A request to the server will be made first and
   * after that it will be deleted.
   */
  async deleteGroupBy(
    { dispatch, commit },
    { view, groupBy, readOnly = false }
  ) {
    commit('SET_GROUP_BY_LOADING', { groupBy, value: true })

    try {
      if (!readOnly) {
        await GroupByService(this.$client).delete(groupBy.id)
      }
      dispatch('forceDeleteGroupBy', { view, groupBy })
    } catch (error) {
      commit('SET_GROUP_BY_LOADING', { groupBy, value: false })
      throw error
    }
  },
  /**
   * Forcefully delete an existing view groupBy without making a request to the backend.
   */
  forceDeleteGroupBy({ commit }, { view, groupBy }) {
    commit('DELETE_GROUP_BY', { view, id: groupBy.id })
  },
  /**
   * When a field is deleted the related group bys are also automatically deleted in the
   * backend so they need to be removed here.
   */
  deleteFieldGroupBys({ commit, getters }, { field }) {
    getters.getAll.forEach((view) => {
      commit('DELETE_FIELD_GROUP_BYS', { view, fieldId: field.id })
    })
  },

  /**
   * Is called when a field is restored. Will force create all filters and sortings
   * provided along with the field.
   */
  fieldRestored({ dispatch, commit, getters }, { field, fieldType, view }) {
    dispatch('resetFieldsFiltersSortsAndGroupBysInView', { field, view })
  },
  /**
   * Called when a field is restored. Will force create all filters and sortings
   * provided along with the field.
   */
  resetFieldsFiltersSortsAndGroupBysInView(
    { dispatch, commit, getters },
    { field, view }
  ) {
    if (field.filters != null) {
      commit('DELETE_FIELD_FILTERS', { view, fieldId: field.id })
      field.filters
        .filter((filter) => filter.view === view.id)
        .forEach((filter) => {
          dispatch('forceCreateFilter', { view, values: filter })
        })
    }
    if (field.sortings != null) {
      commit('DELETE_FIELD_SORTINGS', { view, fieldId: field.id })
      field.sortings
        .filter((sorting) => sorting.view === view.id)
        .forEach((sorting) => {
          dispatch('forceCreateSort', { view, values: sorting })
        })
    }
    if (field.group_bys != null) {
      commit('DELETE_FIELD_GROUP_BYS', { view, fieldId: field.id })
      field.group_bys
        .filter((groupBy) => groupBy.view === view.id)
        .forEach((groupBy) => {
          dispatch('forceCreateSort', { view, values: groupBy })
        })
    }
  },
  /**
   * Is called when a field is updated. It will check if there are filters related
   * to the delete field.
   */
  fieldUpdated({ dispatch, commit, getters }, { field, fieldType }) {
    getters.getAll.forEach((view) => {
      // Remove all filters are not compatible anymore.
      view.filters
        .filter((filter) => filter.field === field.id)
        .forEach((filter) => {
          const filterType = this.$registry.get('viewFilter', filter.type)
          const compatible = filterType.fieldIsCompatible(field)
          if (!compatible) {
            commit('DELETE_FILTER', { view, id: filter.id })
          }
        })

      // Remove all sorts are not compatible anymore.
      view.sortings
        .filter((sort) => sort.field === field.id)
        .forEach((sort) => {
          const sortTypes = fieldType.getSortTypes(field)
          const compatible =
            fieldType.getCanSortInView(field) &&
            Object.prototype.hasOwnProperty.call(sortTypes, sort.type)
          if (!compatible) {
            dispatch('deleteFieldSortings', { field })
          }
        })

      // Remove all sorts are not compatible anymore.
      view.group_bys
        .filter((groupBy) => groupBy.field === field.id)
        .forEach((groupBy) => {
          const sortTypes = fieldType.getSortTypes(field)
          const compatible =
            fieldType.getCanSortInView(field) &&
            Object.prototype.hasOwnProperty.call(sortTypes, groupBy.type)
          if (!compatible) {
            dispatch('deleteFieldGroupBys', { field })
          }
        })
    })
  },
  /**
   * Is called when a field is deleted. It will remove all filters and sortings
   * related to the field.
   */
  fieldDeleted({ dispatch }, { field }) {
    dispatch('deleteFieldFilters', { field })
    dispatch('deleteFieldSortings', { field })
    dispatch('deleteFieldGroupBys', { field })
  },
}

export const getters = {
  hasSelected(state) {
    return Object.prototype.hasOwnProperty.call(state.selected, '_')
  },
  getSelected(state) {
    return state.selected
  },
  getSelectedId(state) {
    return state.selected.id || 0
  },
  get: (state) => (id) => {
    return state.items.find((item) => item.id === id)
  },
  first(state, getters) {
    const items = getters.getAllOrdered
    return items.length > 0 ? items[0] : null
  },
  // currently only used during unit tests:
  defaultId: (state) => {
    return state.defaultViewId
  },
  default: (state, getters) => {
    return getters.get(state.defaultViewId)
  },
  getAll(state) {
    return state.items
  },
  getAllOrdered(state) {
    return state.items.map((item) => item).sort((a, b) => a.order - b.order)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
