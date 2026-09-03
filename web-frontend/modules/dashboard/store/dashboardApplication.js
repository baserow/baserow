import { useNuxtApp } from '#app'
import WidgetService from '@baserow/modules/dashboard/services/widget'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'
import IntegrationService from '@baserow/modules/core/services/integration'
import debounce from 'lodash/debounce'

export const state = () => ({
  dashboardId: null,
  dashboardGeneration: 0,
  widgetFetchGeneration: 0,
  dataSourceCollectionFetchGeneration: 0,
  dataSourceDispatchGenerations: {},
  dataSourceMutationGenerations: {},
  loading: false,
  editMode: false,
  selectedWidgetId: null,
  widgets: [],
  dataSources: [],
  integrations: [],
  // A cache for data that has been
  // returned as a result of dispatching
  // a data source. The keys are data source ids.
  data: {},
})

let debouncedWidgetUpdate = null

const normalizeDashboardFetchRequest = (request, state, generationKey) => {
  const requestValues =
    typeof request === 'object' && request !== null
      ? request
      : { dashboardId: request }

  return {
    dashboardId: requestValues.dashboardId,
    dashboardGeneration:
      requestValues.dashboardGeneration ?? state.dashboardGeneration,
    generation: requestValues.generation ?? state[generationKey],
  }
}

const normalizeDataSourceRequestContext = (request, state) => {
  const requestValues =
    typeof request === 'object' && request !== null
      ? request
      : { dataSourceId: request }

  return {
    dataSourceId: requestValues.dataSourceId,
    dashboardId: requestValues.dashboardId ?? state.dashboardId,
    dashboardGeneration:
      requestValues.dashboardGeneration ?? state.dashboardGeneration,
  }
}

const getDataSourceDispatchGeneration = (state, dataSourceId) =>
  state.dataSourceDispatchGenerations[dataSourceId] ?? 0

const getDataSourceMutationGeneration = (state, dataSourceId) =>
  state.dataSourceMutationGenerations[dataSourceId] ?? 0

const getDataSourceDispatchRequest = (request, state) => {
  const requestContext = normalizeDataSourceRequestContext(request, state)
  return {
    ...requestContext,
    generation: getDataSourceDispatchGeneration(
      state,
      requestContext.dataSourceId
    ),
  }
}

const getDataSourceMutationRequest = (request, state) => {
  const requestContext = normalizeDataSourceRequestContext(request, state)
  return {
    ...requestContext,
    generation: getDataSourceMutationGeneration(
      state,
      requestContext.dataSourceId
    ),
  }
}

const isDashboardRequestCurrent = (state, request) => {
  return (
    state.dashboardId === request.dashboardId &&
    state.dashboardGeneration === request.dashboardGeneration
  )
}

const isFetchRequestCurrent = (state, request, generationKey) => {
  return (
    isDashboardRequestCurrent(state, request) &&
    state[generationKey] === request.generation
  )
}

const isDataSourceDispatchCurrent = (state, request) => {
  return (
    isDashboardRequestCurrent(state, request) &&
    state.dataSources.some(
      (dataSource) => dataSource.id === request.dataSourceId
    ) &&
    getDataSourceDispatchGeneration(state, request.dataSourceId) ===
      request.generation
  )
}

const isDataSourceMutationCurrent = (state, request) => {
  return (
    isDashboardRequestCurrent(state, request) &&
    state.dataSources.some(
      (dataSource) => dataSource.id === request.dataSourceId
    ) &&
    getDataSourceMutationGeneration(state, request.dataSourceId) ===
      request.generation
  )
}

const refreshAfterWidgetCreation = async (dispatch, dashboard) => {
  const refreshes = [
    () => dispatch('fetchNewDataSources', dashboard.id),
    () => dispatch('application/refreshPermissions', dashboard, { root: true }),
  ]
  const results = await Promise.allSettled(
    refreshes.map((refresh) => Promise.resolve().then(refresh))
  )
  const retries = results.flatMap((result, index) => {
    return result.status === 'rejected'
      ? [Promise.resolve().then(refreshes[index])]
      : []
  })

  await Promise.allSettled(retries)
}

export const mutations = {
  RESET(state) {
    state.dashboardId = null
    state.dashboardGeneration += 1
    state.widgetFetchGeneration += 1
    state.dataSourceCollectionFetchGeneration += 1
    state.dataSourceDispatchGenerations = {}
    state.dataSourceMutationGenerations = {}
    state.editMode = false
    state.selectedWidgetId = null
    state.widgets = []
    state.dataSources = []
    state.integrations = []
    state.data = {}
  },
  SET_DASHBOARD_ID(state, dashboardId) {
    if (state.dashboardId !== dashboardId) {
      state.dashboardGeneration += 1
      state.widgetFetchGeneration += 1
      state.dataSourceCollectionFetchGeneration += 1
      state.dataSourceDispatchGenerations = {}
      state.dataSourceMutationGenerations = {}
    }
    state.dashboardId = dashboardId
  },
  INVALIDATE_WIDGET_FETCH(state) {
    state.widgetFetchGeneration += 1
  },
  INVALIDATE_DATA_SOURCE_COLLECTION_FETCH(state) {
    state.dataSourceCollectionFetchGeneration += 1
  },
  INVALIDATE_DATA_SOURCE_DISPATCH(state, dataSourceId) {
    state.dataSourceDispatchGenerations[dataSourceId] =
      getDataSourceDispatchGeneration(state, dataSourceId) + 1
  },
  INVALIDATE_DATA_SOURCE_MUTATION(state, dataSourceId) {
    state.dataSourceMutationGenerations[dataSourceId] =
      getDataSourceMutationGeneration(state, dataSourceId) + 1
  },
  TOGGLE_EDIT_MODE(state) {
    state.editMode = !state.editMode
  },
  ADD_WIDGET(state, widget) {
    const existingWidget = state.widgets.find(
      (existingWidget) => existingWidget.id === widget.id
    )
    if (existingWidget) {
      Object.assign(existingWidget, widget)
    } else {
      state.widgets.push(widget)
    }
  },
  SET_WIDGETS(state, widgets) {
    state.widgets = widgets
    if (!widgets.some((widget) => widget.id === state.selectedWidgetId)) {
      state.selectedWidgetId = null
    }
  },
  ADD_DATA_SOURCE(state, dataSource) {
    const existingDataSource = state.dataSources.find(
      (existingDataSource) => existingDataSource.id === dataSource.id
    )
    if (existingDataSource) {
      Object.assign(existingDataSource, dataSource)
    } else {
      state.dataSources.push(dataSource)
    }
  },
  SET_DATA_SOURCES(state, dataSources) {
    const dataSourceIds = new Set(dataSources.map(({ id }) => id))

    for (const existingDataSource of state.dataSources) {
      if (!dataSourceIds.has(existingDataSource.id)) {
        state.dataSourceDispatchGenerations[existingDataSource.id] =
          getDataSourceDispatchGeneration(state, existingDataSource.id) + 1
        state.dataSourceMutationGenerations[existingDataSource.id] =
          getDataSourceMutationGeneration(state, existingDataSource.id) + 1
        delete state.data[existingDataSource.id]
      }
    }

    const existingDataSourcesById = Object.fromEntries(
      state.dataSources.map((dataSource) => [dataSource.id, dataSource])
    )
    state.dataSources = dataSources.map((dataSource) => {
      const existingDataSource = existingDataSourcesById[dataSource.id]
      if (existingDataSource) {
        Object.assign(existingDataSource, dataSource)
        return existingDataSource
      }
      return dataSource
    })
  },
  UPDATE_DATA_SOURCE(state, { dataSourceId, values }) {
    const dataSource = state.dataSources.find(
      (dataSource) => dataSource.id === dataSourceId
    )
    if (dataSource) {
      Object.assign(dataSource, values)
    } else {
      state.dataSources.push({ id: dataSourceId, ...values })
    }
  },
  UPDATE_DATA(state, { dataSourceId, values }) {
    if (state.data[dataSourceId] === undefined) {
      state.data[dataSourceId] = {}
    }
    state.data = {
      ...state.data,
      [dataSourceId]: { ...values },
    }
  },
  ADD_INTEGRATION(state, integration) {
    state.integrations.push(integration)
  },
  SELECT_WIDGET(state, widgetId) {
    state.selectedWidgetId = widgetId
  },
  UPDATE_WIDGET(state, { widgetId, values }) {
    const widget = state.widgets.find((widget) => widget.id === widgetId)
    if (!widget) {
      return
    }
    // In Vue 3, direct assignment works thanks to Proxy-based reactivity
    if (Array.isArray(values.series_config)) {
      widget.series_config = [...values.series_config]
    }
    Object.assign(widget, values)
  },
  UPDATE_WIDGET_LAYOUTS(state, layouts) {
    const widgetsById = new Map(
      state.widgets.map((widget) => [widget.id, widget])
    )
    layouts.forEach(({ id, grid_x, grid_y, grid_width, grid_height }) => {
      const widget = widgetsById.get(id)
      if (widget) {
        Object.assign(widget, { grid_x, grid_y, grid_width, grid_height })
      }
    })
  },
  DELETE_WIDGET(state, widgetId) {
    const index = state.widgets.findIndex((widget) => widget.id === widgetId)
    if (index !== -1) {
      state.widgets.splice(index, 1)
    }
    if (state.selectedWidgetId === widgetId) {
      state.selectedWidgetId = null
    }
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
}

export const actions = {
  setLoading({ commit }, value) {
    commit('SET_LOADING', value)
  },
  reset({ commit }) {
    commit('RESET')
  },
  toggleEditMode({ commit }) {
    commit('TOGGLE_EDIT_MODE')
  },
  enterEditMode({ getters, commit }) {
    if (!getters.isEditMode) {
      commit('TOGGLE_EDIT_MODE')
    }
  },
  selectWidget({ commit }, widgetId) {
    commit('SELECT_WIDGET', widgetId)
  },
  updateWidget(
    { state, commit, dispatch },
    { widgetId, values, originalValues }
  ) {
    return new Promise((resolve, reject) => {
      const { $client } = this
      commit('INVALIDATE_WIDGET_FETCH')
      const request = normalizeDashboardFetchRequest(
        state.dashboardId,
        state,
        'widgetFetchGeneration'
      )
      commit('UPDATE_WIDGET', { widgetId, values })

      let previousOriginalValues = originalValues
      if (debouncedWidgetUpdate) {
        debouncedWidgetUpdate.cancel()
        previousOriginalValues = debouncedWidgetUpdate.originalValues
      }

      debouncedWidgetUpdate = debounce(async () => {
        try {
          await WidgetService($client).update(widgetId, values)
          debouncedWidgetUpdate = null
          if (
            isDashboardRequestCurrent(state, request) &&
            !isFetchRequestCurrent(state, request, 'widgetFetchGeneration')
          ) {
            await dispatch('fetchWidgets', request.dashboardId)
          }
          resolve()
        } catch (error) {
          if (isFetchRequestCurrent(state, request, 'widgetFetchGeneration')) {
            commit('UPDATE_WIDGET', {
              widgetId,
              values: previousOriginalValues,
            })
          } else if (isDashboardRequestCurrent(state, request)) {
            await dispatch('fetchWidgets', request.dashboardId)
          }
          reject(error)
        }
      }, 1000)
      debouncedWidgetUpdate.originalValues = previousOriginalValues
      debouncedWidgetUpdate()
    })
  },
  async handleWidgetUpdated({ state, commit, dispatch }, widget) {
    commit('INVALIDATE_WIDGET_FETCH')
    if (
      state.loading ||
      !state.widgets.some((existingWidget) => existingWidget.id === widget.id)
    ) {
      await dispatch('fetchWidgets', state.dashboardId)
      return
    }
    commit('UPDATE_WIDGET', { widgetId: widget.id, values: widget })
  },
  async updateDataSource(
    { state, commit, dispatch },
    { dataSourceId, values, widget }
  ) {
    const { $client, $registry } = this
    const previousData = state.data[dataSourceId]
    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    commit('INVALIDATE_DATA_SOURCE_DISPATCH', dataSourceId)
    commit('INVALIDATE_DATA_SOURCE_MUTATION', dataSourceId)
    const request = getDataSourceMutationRequest({ dataSourceId }, state)
    commit('UPDATE_DATA', { dataSourceId, values: null })

    let data
    try {
      const response = await DataSourceService($client).update(
        dataSourceId,
        values
      )
      data = response.data
    } catch (error) {
      if (isDataSourceMutationCurrent(state, request)) {
        const hasPreviousData =
          previousData && Object.keys(previousData).length > 0
        commit('UPDATE_DATA', {
          dataSourceId,
          values: hasPreviousData ? previousData : { _error: true },
        })
      }
      throw error
    }

    if (!isDataSourceMutationCurrent(state, request)) {
      return
    }

    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    commit('UPDATE_DATA_SOURCE', {
      dataSourceId,
      values: data,
    })
    try {
      if (widget) {
        const widgetType = $registry.get('dashboardWidget', widget.type)
        await widgetType.dataSourceUpdated(widget, data)
        if (!isDataSourceMutationCurrent(state, request)) {
          return
        }
      }

      await dispatch('dispatchDataSource', {
        dataSourceId,
        dashboardId: request.dashboardId,
        dashboardGeneration: request.dashboardGeneration,
      })
    } catch (error) {
      if (isDataSourceMutationCurrent(state, request)) {
        commit('UPDATE_DATA', {
          dataSourceId,
          values: { _error: true },
        })
      }
      throw error
    }
  },
  async handleDataSourceUpdated({ state, commit, dispatch }, dataSource) {
    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    commit('INVALIDATE_DATA_SOURCE_MUTATION', dataSource.id)
    commit('UPDATE_DATA_SOURCE', {
      dataSourceId: dataSource.id,
      values: dataSource,
    })
    await dispatch('dispatchDataSource', {
      dataSourceId: dataSource.id,
      dashboardId: state.dashboardId,
      dashboardGeneration: state.dashboardGeneration,
    })
  },
  async fetchInitial({ state, commit, dispatch }, { dashboardId, forEditing }) {
    const { $client } = this
    commit('RESET')
    commit('SET_DASHBOARD_ID', dashboardId)
    const request = {
      dashboardId,
      dashboardGeneration: state.dashboardGeneration,
    }

    let widgets
    do {
      widgets = await dispatch('fetchWidgets', dashboardId)
    } while (widgets === undefined && isDashboardRequestCurrent(state, request))
    if (!isDashboardRequestCurrent(state, request)) {
      return
    }

    await dispatch('setLoading', false)
    let dataSources
    do {
      dataSources = await dispatch('fetchNewDataSources', dashboardId)
    } while (
      dataSources === undefined &&
      isDashboardRequestCurrent(state, request)
    )
    if (!isDashboardRequestCurrent(state, request)) {
      return
    }

    if (forEditing) {
      const { data: integrationsData } =
        await IntegrationService($client).fetchAll(dashboardId)
      if (!isDashboardRequestCurrent(state, request)) {
        return
      }
      integrationsData.forEach((integration) => {
        commit('ADD_INTEGRATION', integration)
      })
    }
  },
  async fetchWidgets({ state, commit }, requestValues) {
    const { $client } = this
    const dashboardId =
      typeof requestValues === 'object' && requestValues !== null
        ? requestValues.dashboardId
        : requestValues
    if (dashboardId !== state.dashboardId) {
      return
    }
    commit('INVALIDATE_WIDGET_FETCH')
    const request = normalizeDashboardFetchRequest(
      dashboardId,
      state,
      'widgetFetchGeneration'
    )
    const { data } = await WidgetService($client).getAllWidgets(
      request.dashboardId
    )
    if (!isFetchRequestCurrent(state, request, 'widgetFetchGeneration')) {
      return
    }
    commit('SET_WIDGETS', data)
    return data
  },
  async fetchNewDataSources(
    { state, commit, dispatch, getters },
    requestValues
  ) {
    const { $client } = this
    const dashboardId =
      typeof requestValues === 'object' && requestValues !== null
        ? requestValues.dashboardId
        : requestValues
    if (dashboardId !== state.dashboardId) {
      return
    }
    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    const request = normalizeDashboardFetchRequest(
      dashboardId,
      state,
      'dataSourceCollectionFetchGeneration'
    )
    const { data: dataSourcesData } = await DataSourceService(
      $client
    ).getAllDataSources(request.dashboardId)

    if (
      !isFetchRequestCurrent(
        state,
        request,
        'dataSourceCollectionFetchGeneration'
      )
    ) {
      return
    }

    const dataSourceIdsToDispatch = new Set(
      dataSourcesData.flatMap((dataSource) => {
        const existingDataSource = getters.getDataSourceById(dataSource.id)
        const existingData = state.data[dataSource.id]
        const shouldDispatch =
          !existingDataSource ||
          !existingData ||
          Object.keys(existingData).length === 0 ||
          existingData._error === true
        return shouldDispatch ? [dataSource.id] : []
      })
    )
    commit('SET_DATA_SOURCES', dataSourcesData)

    await Promise.all(
      dataSourcesData.map(async (dataSource) => {
        if (
          !isFetchRequestCurrent(
            state,
            request,
            'dataSourceCollectionFetchGeneration'
          )
        ) {
          return
        }
        if (!dataSourceIdsToDispatch.has(dataSource.id)) {
          return
        }
        await dispatch('dispatchDataSource', {
          dataSourceId: dataSource.id,
          dashboardId: request.dashboardId,
          dashboardGeneration: request.dashboardGeneration,
        })
      })
    )
    if (
      !isFetchRequestCurrent(
        state,
        request,
        'dataSourceCollectionFetchGeneration'
      )
    ) {
      return
    }
    return dataSourcesData
  },
  async createWidget({ state, dispatch }, { dashboard, widget }) {
    const { $client } = this
    const request = {
      dashboardId: dashboard.id,
      dashboardGeneration: state.dashboardGeneration,
    }
    const { data: widgetData } = await WidgetService($client).create(
      dashboard.id,
      widget
    )
    if (!isDashboardRequestCurrent(state, request)) {
      return widgetData
    }
    const createdWidget = await dispatch('handleNewWidgetCreated', widgetData)
    if (!isDashboardRequestCurrent(state, request)) {
      return createdWidget
    }
    // The POST above is the creation boundary. Refreshing related client state must
    // never turn a persisted widget into an apparent creation failure.
    await refreshAfterWidgetCreation(dispatch, dashboard)
    return createdWidget
  },
  handleNewWidgetCreated({ state, commit, dispatch }, widget) {
    if (widget.dashboard_id !== state.dashboardId) {
      return widget
    }
    commit('INVALIDATE_WIDGET_FETCH')
    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    commit('ADD_WIDGET', widget)
    dispatch('selectWidget', widget.id)
    return widget
  },
  async dispatchDataSource({ state, commit }, requestValues) {
    const { $client } = this
    const requestContext = normalizeDataSourceRequestContext(
      requestValues,
      state
    )
    if (
      !isDashboardRequestCurrent(state, requestContext) ||
      !state.dataSources.some(
        (dataSource) => dataSource.id === requestContext.dataSourceId
      )
    ) {
      return
    }

    commit('INVALIDATE_DATA_SOURCE_DISPATCH', requestContext.dataSourceId)
    const request = getDataSourceDispatchRequest(requestContext, state)
    commit('UPDATE_DATA', { dataSourceId: request.dataSourceId, values: null })
    try {
      const { data } = await DataSourceService($client).dispatch(
        request.dataSourceId
      )
      if (!isDataSourceDispatchCurrent(state, request)) {
        return
      }
      commit('UPDATE_DATA', {
        dataSourceId: request.dataSourceId,
        values: data,
      })
    } catch (error) {
      if (!isDataSourceDispatchCurrent(state, request)) {
        return
      }
      commit('UPDATE_DATA', {
        dataSourceId: request.dataSourceId,
        values: { _error: true },
      })
    }
  },
  async deleteWidget({ state, commit, dispatch }, widgetId) {
    const { $client } = this
    commit('INVALIDATE_WIDGET_FETCH')
    const request = normalizeDashboardFetchRequest(
      state.dashboardId,
      state,
      'widgetFetchGeneration'
    )
    await WidgetService($client).delete(widgetId)
    if (!isDashboardRequestCurrent(state, request)) {
      return
    }
    await dispatch('fetchWidgets', request.dashboardId)
  },
  async handleWidgetDeleted({ state, commit, dispatch }, widgetId) {
    const widgetExists = state.widgets.some((widget) => widget.id === widgetId)
    commit('INVALIDATE_WIDGET_FETCH')
    if (state.loading || !widgetExists) {
      await dispatch('fetchWidgets', state.dashboardId)
      return
    }
    commit('DELETE_WIDGET', widgetId)
  },
  async updateWidgetLayout({ state, commit }, { dashboardId, layout }) {
    const { $client } = this
    commit('INVALIDATE_WIDGET_FETCH')
    const request = normalizeDashboardFetchRequest(
      dashboardId,
      state,
      'widgetFetchGeneration'
    )
    const { data } = await WidgetService($client).updateLayout(
      dashboardId,
      layout
    )
    if (!isFetchRequestCurrent(state, request, 'widgetFetchGeneration')) {
      return data
    }
    commit('UPDATE_WIDGET_LAYOUTS', data)
    return data
  },
  async handleWidgetsLayoutUpdated({ state, commit, dispatch }) {
    commit('INVALIDATE_WIDGET_FETCH')
    commit('INVALIDATE_DATA_SOURCE_COLLECTION_FETCH')
    await Promise.allSettled([
      dispatch('fetchWidgets', state.dashboardId),
      dispatch('fetchNewDataSources', state.dashboardId),
    ])
  },
}

export const getters = {
  getDashboardId(state) {
    return state.dashboardId
  },
  isEditMode(state) {
    return state.editMode
  },
  isLoading(state) {
    return state.loading
  },
  isEmpty(state) {
    return state.widgets.length === 0
  },
  getWidgetById: (state, getters) => (widgetId) => {
    return state.widgets.find((widget) => widget.id === widgetId)
  },
  getWidgets(state) {
    return state.widgets.toSorted((first, second) => {
      const byY = (first.grid_y ?? 0) - (second.grid_y ?? 0)
      if (byY !== 0) {
        return byY
      }

      const byX = (first.grid_x ?? 0) - (second.grid_x ?? 0)
      if (byX !== 0) {
        return byX
      }

      return first.id - second.id
    })
  },
  getSelectedWidgetId(state) {
    return state.selectedWidgetId
  },
  getSelectedWidget(state) {
    return state.widgets.find((widget) => widget.id === state.selectedWidgetId)
  },
  getDataSourceById: (state, getters) => (dataSourceId) => {
    return state.dataSources.find(
      (dataSource) => dataSource.id === dataSourceId
    )
  },
  getData(state) {
    return state.data
  },
  getDataForDataSource: (state, getters) => (dataSourceId) => {
    return state.data[dataSourceId]
  },
  getIntegrations(state) {
    return state.integrations
  },
  getIntegrationById: (state) => (integrationId) => {
    return state.integrations.find(
      (integration) => integration.id === integrationId
    )
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
