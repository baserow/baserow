import { useNuxtApp } from '#app'
import WidgetService from '@baserow/modules/dashboard/services/widget'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'
import IntegrationService from '@baserow/modules/core/services/integration'
import debounce from 'lodash/debounce'

export const state = () => ({
  dashboardId: null,
  // Identifies the most recent `fetchInitial` call, so that a slower one that
  // was started earlier can tell it has been superseded, also by a fetch of the
  // same dashboard.
  fetchRequestId: 0,
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

export const mutations = {
  INCREMENT_FETCH_REQUEST_ID(state) {
    state.fetchRequestId += 1
  },
  RESET(state) {
    state.dashboardId = null
    state.editMode = false
    state.selectedWidgetId = null
    state.widgets = []
    state.dataSources = []
    state.integrations = []
    state.data = {}
  },
  SET_DASHBOARD_ID(state, dashboardId) {
    state.dashboardId = dashboardId
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
    state.dataSources.push(dataSource)
  },
  UPDATE_DATA_SOURCE(state, { dataSourceId, values }) {
    const dataSource = state.dataSources.find(
      (dataSource) => dataSource.id === dataSourceId
    )
    Object.assign(dataSource, values)
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
      state.widgets.push(values)
      return
    }
    // In Vue 3, direct assignment works thanks to Proxy-based reactivity
    if (Array.isArray(values.series_config)) {
      widget.series_config = [...values.series_config]
    }
    Object.assign(widget, values)
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
  updateWidget({ commit }, { widgetId, values, originalValues }) {
    return new Promise((resolve, reject) => {
      const { $client } = this
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
          resolve()
        } catch (error) {
          commit('UPDATE_WIDGET', { widgetId, values: previousOriginalValues })
          reject(error)
        }
      }, 1000)
      debouncedWidgetUpdate.originalValues = previousOriginalValues
      debouncedWidgetUpdate()
    })
  },
  handleWidgetUpdated({ commit }, widget) {
    commit('UPDATE_WIDGET', { widgetId: widget.id, values: widget })
  },
  async updateDataSource(
    { commit, dispatch },
    { dataSourceId, values, widget }
  ) {
    const { $client, $registry } = this
    commit('UPDATE_DATA', { dataSourceId, values: null })
    const { data } = await DataSourceService($client).update(
      dataSourceId,
      values
    )
    if (widget) {
      const widgetType = $registry.get('dashboardWidget', widget.type)
      await widgetType.dataSourceUpdated(widget, data)
    }
    await dispatch('handleDataSourceUpdated', data)
  },
  async handleDataSourceUpdated({ commit, dispatch }, dataSource) {
    commit('UPDATE_DATA_SOURCE', {
      dataSourceId: dataSource.id,
      values: dataSource,
    })
    try {
      await dispatch('dispatchDataSource', dataSource.id)
    } catch (error) {
      commit('UPDATE_DATA', {
        dataSourceId: dataSource.id,
        values: { _error: true },
      })
    }
  },
  async fetchInitial({ commit, dispatch, state }, { dashboardId, forEditing }) {
    const { $client } = this
    commit('INCREMENT_FETCH_REQUEST_ID')
    const requestId = state.fetchRequestId
    commit('RESET')
    commit('SET_LOADING', true)
    commit('SET_DASHBOARD_ID', dashboardId)
    const { data } = await WidgetService($client).getAllWidgets(dashboardId)
    // The dashboard page fetches without blocking the navigation, so another
    // fetch can have been started while a request was running, for another
    // dashboard or for the same one again. The store must then not receive the
    // widgets and data sources of the superseded one.
    if (requestId !== state.fetchRequestId) {
      return
    }
    commit('SET_WIDGETS', data)
    // The widgets are known now, so they can be rendered while their data is
    // still being fetched. They show a loading state of their own.
    commit('SET_LOADING', false)
    await dispatch('fetchNewDataSources', { dashboardId, requestId })

    if (forEditing) {
      const { data: integrationsData } =
        await IntegrationService($client).fetchAll(dashboardId)
      if (requestId !== state.fetchRequestId) {
        return
      }
      integrationsData.forEach((integration) => {
        commit('ADD_INTEGRATION', integration)
      })
    }
  },
  async fetchNewDataSources(
    { commit, dispatch, getters, state },
    { dashboardId, requestId }
  ) {
    const { $client } = this
    const { data: dataSourcesData } =
      await DataSourceService($client).getAllDataSources(dashboardId)
    if (requestId !== state.fetchRequestId) {
      return
    }
    await Promise.all(
      dataSourcesData.map(async (dataSource) => {
        if (!getters.getDataSourceById(dataSource.id)) {
          commit('ADD_DATA_SOURCE', dataSource)
        }
        if (!getters.getDataForDataSource(dataSource.id)) {
          await dispatch('dispatchDataSource', dataSource.id)
        }
      })
    )
  },
  async createWidget({ dispatch }, { dashboard, widget }) {
    const { $client } = this
    const { data: widgetData } = await WidgetService($client).create(
      dashboard.id,
      widget
    )
    const createdWidget = await dispatch('handleNewWidgetCreated', widgetData)
    dispatch('selectWidget', createdWidget.id)
    await dispatch('application/refreshPermissions', dashboard, { root: true })
    return createdWidget
  },
  async handleNewWidgetCreated({ commit, dispatch, state }, widget) {
    commit('ADD_WIDGET', widget)
    await dispatch('fetchNewDataSources', {
      dashboardId: widget.dashboard_id,
      requestId: state.fetchRequestId,
    })
    return widget
  },
  async dispatchDataSource({ commit }, dataSourceId) {
    const { $client } = this
    commit('UPDATE_DATA', { dataSourceId, values: null })
    try {
      const { data } = await DataSourceService($client).dispatch(dataSourceId)
      commit('UPDATE_DATA', { dataSourceId, values: data })
    } catch (error) {
      commit('UPDATE_DATA', { dataSourceId, values: { _error: true } })
    }
  },
  async deleteWidget({ state, commit }, widgetId) {
    const { $client } = this
    await WidgetService($client).delete(widgetId)
    const { data } = await WidgetService($client).getAllWidgets(
      state.dashboardId
    )
    commit('SET_WIDGETS', data)
  },
  handleWidgetDeleted({ commit }, widgetId) {
    commit('DELETE_WIDGET', widgetId)
  },
  async updateWidgetLayout({ commit }, { dashboardId, layout }) {
    const { $client } = this
    const { data } = await WidgetService($client).updateLayout(
      dashboardId,
      layout
    )
    commit('SET_WIDGETS', data)
    return data
  },
  handleWidgetsLayoutUpdated({ commit }, widgets) {
    commit('SET_WIDGETS', widgets)
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
