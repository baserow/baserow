import isEqual from 'lodash/isEqual'
import cloneDeep from 'lodash/cloneDeep'
import FilterService from '@baserow/modules/dashboard/services/filter'
import {
  filterHasOptions,
  getDataSourceFilterInputs,
  getReferencedDashboardFilterId,
  hasActiveDashboardFilter,
} from '@baserow/modules/dashboard/utils/filter'

import { createLatestCollectionFetch } from '@baserow/modules/dashboard/utils/requests'

const fetchFilterCollection = createLatestCollectionFetch()
const filterSourceRefreshes = new WeakMap()

export const filterState = () => ({
  filters: [],
  selectedFilterId: null,
  filterFetchGeneration: 0,
  filterOptionGenerations: {},
  filterOptions: {},
  filterDataSourceInputs: {},
  refreshing: false,
})

const dashboardRequest = (state, rootGetters) => ({
  id: state.dashboardId,
  generation: state.dashboardGeneration,
  userId: rootGetters['auth/getUserId'],
})
const isCurrent = (state, request, rootGetters) =>
  state.dashboardId === request.id &&
  state.dashboardGeneration === request.generation &&
  request.userId === rootGetters['auth/getUserId']
const emptyOptions = () => ({
  results: [],
  next: null,
  snapshot: null,
  checkedValues: [],
  unavailable: [],
  loading: false,
  error: false,
  errorCode: null,
  loaded: false,
})

const uncheckedOptionValues = (options, selected) => {
  const knownValues = new Set([...options.checkedValues, ...options.results])
  return [...new Set(selected)].filter((value) => !knownValues.has(value))
}

const invalidateOptions = (state, filterId) => {
  state.filterOptionGenerations[filterId] =
    (state.filterOptionGenerations[filterId] ?? 0) + 1
  if (state.filterOptions[filterId])
    state.filterOptions[filterId].loading = false
}

export const filterMutations = {
  RECORD_FILTER_DISPATCH(state, { dataSourceId, serviceType }) {
    const source = state.dataSources.find(({ id }) => id === dataSourceId)
    // Record when queued, not when completed: an echo must not restart a request.
    state.filterDataSourceInputs[dataSourceId] = cloneDeep(
      getDataSourceFilterInputs(source, state.filters, serviceType)
    )
  },
  INVALIDATE_FILTER_FETCH(state) {
    state.filterFetchGeneration += 1
  },
  INVALIDATE_FILTER_OPTIONS: invalidateOptions,
  SET_FILTERS(state, filters) {
    const previous = new Map(state.filters.map((filter) => [filter.id, filter]))
    state.filters = filters
    const byId = new Map(filters.map((filter) => [filter.id, filter]))
    for (const filter of previous.values()) {
      const next = byId.get(filter.id)
      if (
        !next ||
        filter.type !== next.type ||
        !isEqual(filter.formula_value, next.formula_value)
      ) {
        invalidateOptions(state, filter.id)
        delete state.filterOptions[filter.id]
      }
    }
    if (!byId.has(state.selectedFilterId)) state.selectedFilterId = null
  },
  ORDER_FILTERS(state, order) {
    const positions = new Map(order.map((id, index) => [id, index]))
    state.filters.sort(
      (a, b) =>
        (positions.get(a.id) ?? order.length) -
        (positions.get(b.id) ?? order.length)
    )
  },
  SELECT_FILTER(state, filterId) {
    state.selectedFilterId = filterId
    state.selectedWidgetId = null
  },
  SET_FILTER_OPTIONS(state, { filterId, values }) {
    state.filterOptions[filterId] = {
      ...(state.filterOptions[filterId] ?? emptyOptions()),
      ...values,
    }
  },
  SET_FILTER_OPTION_AVAILABILITY(state, { filterId, selected, available }) {
    const options = state.filterOptions[filterId]
    const unavailable = new Set(options.unavailable)
    const availableValues = new Set(available)
    for (const value of selected) {
      if (availableValues.has(value)) unavailable.delete(value)
      else unavailable.add(value)
    }
    options.checkedValues = [
      ...new Set([...options.checkedValues, ...selected]),
    ]
    options.unavailable = [...unavailable]
  },
  SET_REFRESHING(state, value) {
    state.refreshing = value
  },
}

export const filterActions = {
  selectFilter({ commit }, filterId) {
    commit('SELECT_FILTER', filterId)
  },
  fetchFilters({ state, commit, dispatch, rootGetters }) {
    const request = dashboardRequest(state, rootGetters)
    commit('INVALIDATE_FILTER_FETCH')
    const generation = state.filterFetchGeneration
    const current = () => isCurrent(state, request, rootGetters)
    const latest = () => generation === state.filterFetchGeneration
    return fetchFilterCollection(state, {
      isCurrent: current,
      isLatest: latest,
      fetch: async () => {
        const { data } = await FilterService(this.$client).fetchAll(request.id)
        if (!current() || !latest()) return
        const previousValues = new Map(
          state.filters.map(({ id, values }) => [id, values])
        )
        commit('SET_FILTERS', data)
        await Promise.all(
          data
            .filter(
              ({ id, values }) => !isEqual(previousValues.get(id), values)
            )
            .map(({ id }) =>
              dispatch('checkFilterOptionAvailability', { filterId: id })
            )
        )
        return data
      },
    })
  },
  async createFilter({ state, commit, dispatch, rootGetters }, values) {
    const request = dashboardRequest(state, rootGetters)
    const { data } = await FilterService(this.$client).create(
      request.id,
      values
    )
    if (!isCurrent(state, request, rootGetters)) return data
    commit('SELECT_FILTER', data.id)
    await dispatch('enterEditMode')
    // Creation is already committed. Retry reads, never the POST, and distinguish
    // a refresh failure from a failed creation so the user does not create a copy.
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await dispatch('handleFiltersUpdated')
        break
      } catch {
        if (!isCurrent(state, request, rootGetters)) return data
        if (attempt === 1) {
          await dispatch(
            'toast/warning',
            {
              title: this.$i18n.t('dashboardFilter.createdRefreshFailedTitle'),
              message: this.$i18n.t(
                'dashboardFilter.createdRefreshFailedMessage'
              ),
            },
            { root: true }
          )
        }
      }
    }
    return data
  },
  async orderFilters({ state, commit, dispatch, rootGetters }, order) {
    const request = dashboardRequest(state, rootGetters)
    const previousOrder = state.filters.map(({ id }) => id)
    commit('INVALIDATE_FILTER_FETCH')
    commit('ORDER_FILTERS', order)
    const optimisticFilters = state.filters
    try {
      await FilterService(this.$client).order(request.id, order)
    } catch (error) {
      if (
        isCurrent(state, request, rootGetters) &&
        state.filters === optimisticFilters
      ) {
        commit('ORDER_FILTERS', previousOrder)
      }
      throw error
    }
    if (isCurrent(state, request, rootGetters))
      await dispatch('handleFiltersUpdated')
  },
  async updateFilter({ state, dispatch, rootGetters }, { filterId, values }) {
    const request = dashboardRequest(state, rootGetters)
    const { data } = await FilterService(this.$client).update(filterId, values)
    if (!isCurrent(state, request, rootGetters)) return
    // Mutation responses can predate a realtime update. Reconcile every change
    // through the same collection request instead of merging stale snapshots.
    await dispatch('handleFiltersUpdated', { refreshDataSources: false })
    return isCurrent(state, request, rootGetters) ? data : undefined
  },
  async deleteFilter({ state, dispatch, rootGetters }, filterId) {
    const request = dashboardRequest(state, rootGetters)
    await FilterService(this.$client).delete(filterId)
    if (!isCurrent(state, request, rootGetters)) return
    await dispatch('handleFiltersUpdated')
  },
  async handleFiltersUpdated(
    { state, dispatch, rootGetters },
    { refreshDataSources = true } = {}
  ) {
    const request = dashboardRequest(state, rootGetters)
    const previous = filterSourceRefreshes.get(state)
    // Ordinary updates don't change source definitions. A deletion/restoration
    // still requires synchronization, including retrying a previous failed read.
    const refresh =
      refreshDataSources ||
      (previous?.error && isCurrent(state, previous.request, rootGetters))
        ? { request, error: null }
        : null
    if (refresh) filterSourceRefreshes.set(state, refresh)
    const synchronized = (async () => {
      await dispatch('fetchCurrentFilters', {
        dashboardId: request.id,
        dashboardGeneration: request.generation,
      })
      if (!refresh || !isCurrent(state, request, rootGetters)) return
      let sources
      do {
        sources = await dispatch('fetchNewDataSources', {
          dashboardId: request.id,
          dispatchMissing: false,
        })
        // A source mutation can invalidate a read without starting its successor.
      } while (sources === undefined && isCurrent(state, request, rootGetters))
    })()
    if (refresh) {
      refresh.promise = synchronized.catch((error) => {
        refresh.error = error
      })
    }
    await (refresh?.promise ?? synchronized)
    if (!isCurrent(state, request, rootGetters)) return
    // A concurrent structural change may still be reading its source conditions.
    // Share its result/failure before declaring this save synchronized.
    let latest
    do {
      latest = filterSourceRefreshes.get(state)
      if (latest && isCurrent(state, latest.request, rootGetters)) {
        await latest.promise
        if (
          latest.error &&
          isCurrent(state, request, rootGetters) &&
          latest === filterSourceRefreshes.get(state)
        )
          throw latest.error
      }
    } while (
      isCurrent(state, request, rootGetters) &&
      latest !== filterSourceRefreshes.get(state)
    )
    // Compare against the last dispatch, not this event's response: overlapping
    // collection requests can replace each other without losing refresh duties.
    if (isCurrent(state, request, rootGetters))
      await dispatch('dispatchDataSources', { onlyChangedFilters: true })
  },
  async applyFilter({ state, dispatch }, { filterId, values }) {
    const filter = state.filters.find((f) => f.id === filterId)
    if (!filter) return
    const normalized =
      filter.mode === 'input'
        ? values.slice(0, 1).map((value) => value.trim())
        : values
    return dispatch('updateFilter', {
      filterId,
      values: { values: normalized.filter((value) => value !== '') },
    })
  },
  async fetchCurrentFilters({ state, dispatch, rootGetters }, request) {
    const userId = rootGetters['auth/getUserId']
    const current = () =>
      state.dashboardId === request.dashboardId &&
      state.dashboardGeneration === request.dashboardGeneration &&
      rootGetters['auth/getUserId'] === userId
    let filters
    do {
      filters = await dispatch('fetchFilters')
    } while (filters === undefined && current())
    return current() ? filters : undefined
  },
  async preloadFilterOptions({ state, commit, dispatch }, request) {
    const current = () =>
      state.dashboardId === request.dashboardId &&
      state.dashboardGeneration === request.dashboardGeneration
    while (current()) {
      const generation = state.filterFetchGeneration
      await Promise.all(
        state.filters.filter(filterHasOptions).map((filter) =>
          dispatch('fetchFilterOptions', {
            filterId: filter.id,
            useCache: true,
          })
        )
      )
      if (!current()) return
      if (generation === state.filterFetchGeneration) {
        // Choices are ready at first click; widgets can still finish loading.
        commit('SET_LOADING', false)
        return
      }
      // A concurrent configuration change invalidated the choices.
      await dispatch('fetchCurrentFilters', request)
    }
  },
  async fetchFilterOptions(
    { state, commit, dispatch, rootGetters },
    { filterId, more = false, selected, useCache = false } = {}
  ) {
    const filter = state.filters.find((f) => f.id === filterId)
    if (!filter || !filterHasOptions(filter)) return
    const request = dashboardRequest(state, rootGetters)
    const previous = state.filterOptions[filterId] ?? emptyOptions()
    // Reopening shares the initial load and keeps failures visible for Retry.
    if (
      useCache &&
      !more &&
      (previous.loading || previous.loaded || previous.error)
    )
      return dispatch('checkFilterOptionAvailability', { filterId, selected })
    if (more && (previous.loading || previous.next === null)) return
    commit('INVALIDATE_FILTER_OPTIONS', filterId)
    const generation = state.filterOptionGenerations[filterId]
    const current = () =>
      isCurrent(state, request, rootGetters) &&
      generation === state.filterOptionGenerations[filterId] &&
      state.filters.some((f) => f.id === filterId)
    const requestedValues = [...new Set(selected ?? filter.values ?? [])]
    commit('SET_FILTER_OPTIONS', {
      filterId,
      values: {
        loading: true,
        error: false,
        errorCode: null,
        ...(more
          ? {}
          : {
              results: [],
              next: null,
              snapshot: null,
              loaded: false,
            }),
      },
    })
    try {
      const { data } = await FilterService(this.$client).options(filterId, {
        selected: requestedValues,
        ...(more ? { after: previous.next } : {}),
      })
      if (!current()) return
      commit('SET_FILTER_OPTIONS', {
        filterId,
        values: {
          results: more
            ? [...new Set([...previous.results, ...data.results])]
            : data.results,
          next: data.next,
          snapshot: more ? previous.snapshot : data.snapshot,
          ...(more ? {} : { checkedValues: [], unavailable: [] }),
          loaded: true,
          loading: false,
          error: false,
        },
      })
      commit('SET_FILTER_OPTION_AVAILABILITY', {
        filterId,
        selected: requestedValues,
        available: data.available,
      })
      // Saved selections may have changed while this page was loading.
      await dispatch('checkFilterOptionAvailability', { filterId })
    } catch (error) {
      if (!current()) return
      // A failed request never establishes that a selected value disappeared.
      commit('SET_FILTER_OPTIONS', {
        filterId,
        values: {
          loading: false,
          error: true,
          errorCode: error.response?.data?.error ?? null,
        },
      })
    }
  },
  async checkFilterOptionAvailability(
    { state, commit, rootGetters },
    { filterId, selected }
  ) {
    const filter = state.filters.find(({ id }) => id === filterId)
    const options = state.filterOptions[filterId]
    if (
      !filter ||
      !filterHasOptions(filter) ||
      !options?.snapshot ||
      options.error
    )
      return
    const requestedValues = uncheckedOptionValues(
      options,
      selected ?? filter.values ?? []
    )
    if (!requestedValues.length) return
    const request = dashboardRequest(state, rootGetters)
    const snapshot = options.snapshot
    const current = () =>
      isCurrent(state, request, rootGetters) &&
      state.filterOptions[filterId]?.snapshot === snapshot
    try {
      const { data } = await FilterService(this.$client).options(filterId, {
        after: snapshot,
        limit: 1,
        selected: requestedValues,
      })
      if (!current()) return
      // Membership facts from one immutable snapshot can be merged regardless of
      // response order; a check never replaces paginated choices or their cursor.
      commit('SET_FILTER_OPTION_AVAILABILITY', {
        filterId,
        selected: requestedValues,
        available: data.available,
      })
    } catch (error) {
      if (!current()) return
      // A picker's captured selection can outlive the open picker. Only values
      // still saved on this filter should surface a failed availability check.
      const currentValues =
        state.filters.find(({ id }) => id === filterId)?.values ?? []
      const stillNeeded = uncheckedOptionValues(
        state.filterOptions[filterId],
        currentValues
      )
      if (!requestedValues.some((value) => stillNeeded.includes(value))) return
      commit('SET_FILTER_OPTIONS', {
        filterId,
        values: { error: true, errorCode: error.response?.data?.error ?? null },
      })
    }
  },
  async refresh({ state, commit, dispatch, rootGetters }) {
    if (state.refreshing) return
    const request = dashboardRequest(state, rootGetters)
    commit('SET_REFRESHING', true)
    try {
      await dispatch('fetchCurrentFilters', {
        dashboardId: request.id,
        dashboardGeneration: request.generation,
      })
      if (!isCurrent(state, request, rootGetters)) return
      await dispatch('fetchNewDataSources', {
        dashboardId: request.id,
        dispatchMissing: false,
      })
      if (!isCurrent(state, request, rootGetters)) return
      await Promise.allSettled([
        dispatch('dispatchDataSources'),
        ...state.filters
          .filter(filterHasOptions)
          .map((f) => dispatch('fetchFilterOptions', { filterId: f.id })),
      ])
    } finally {
      if (isCurrent(state, request, rootGetters))
        commit('SET_REFRESHING', false)
    }
  },
}

export const filterGetters = {
  hasFilterDataSourceChanges: (state) => (source, registry) =>
    !isEqual(
      state.filterDataSourceInputs[source.id],
      getDataSourceFilterInputs(
        source,
        state.filters,
        registry?.getAll('service')[source.type]
      )
    ),
  isDataSourceFiltered: (state) => (dataSourceId, registry) => {
    const source = state.dataSources.find(({ id }) => id === dataSourceId)
    return (source?.filters ?? []).some((condition) => {
      if (condition.field == null || condition.trashed) return false
      // Only direct dashboard links depend on an applied selection. Other
      // source conditions apply independently, including computed formulas.
      if (getReferencedDashboardFilterId(condition.value) === null) {
        return (
          !registry.get('viewFilter', condition.type).hasEditableValue ||
          Boolean(condition.value?.formula?.trim())
        )
      }
      return hasActiveDashboardFilter(condition.value, state.filters)
    })
  },
  getFilters: (state) => state.filters,
  getSelectedFilter: (state) =>
    state.filters.find((f) => f.id === state.selectedFilterId),
  getAppliedFilterValues: (state) => (filterId) =>
    state.filters.find(({ id }) => id === filterId)?.values ?? [],
  getFilterOptions: (state) => (filterId) =>
    state.filterOptions[filterId] ?? emptyOptions(),
  isRefreshing: (state) => state.refreshing,
}
