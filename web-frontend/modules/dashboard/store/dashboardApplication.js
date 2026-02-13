import { useNuxtApp } from '#app'
import WidgetService from '@baserow/modules/dashboard/services/widget'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'
import IntegrationService from '@baserow/modules/core/services/integration'
import debounce from 'lodash/debounce'

export const state = () => ({
  dashboardId: null,
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
    state.widgets.push(widget)
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
    // In Vue 3, direct assignment works thanks to Proxy-based reactivity
    if (Array.isArray(values.series_config)) {
      widget.series_config = [...values.series_config]
    }
    Object.assign(widget, values)
  },
  DELETE_WIDGET(state, widgetId) {
    const index = state.widgets.findIndex((widget) => widget.id === widgetId)
    state.widgets.splice(index, 1)
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
  async fetchInitial({ commit, dispatch }, { dashboardId, forEditing }) {
    const { $client } = this
    commit('RESET')
    commit('SET_DASHBOARD_ID', dashboardId)
    const { data } = await WidgetService($client).getAllWidgets(dashboardId)
    data.forEach((widget) => {
      commit('ADD_WIDGET', widget)
    })
    await dispatch('setLoading', false)
    await dispatch('fetchNewDataSources', dashboardId)

    if (forEditing) {
      const { data: integrationsData } =
        await IntegrationService($client).fetchAll(dashboardId)
      integrationsData.forEach((integration) => {
        commit('ADD_INTEGRATION', integration)
      })
    }
  },
  async fetchNewDataSources({ commit, dispatch, getters }, dashboardId) {
    const { $client } = this
    const { data: dataSourcesData } =
      await DataSourceService($client).getAllDataSources(dashboardId)
    dataSourcesData.forEach(async (dataSource) => {
      if (!getters.getDataSourceById(dataSource.id)) {
        commit('ADD_DATA_SOURCE', dataSource)
        await dispatch('dispatchDataSource', dataSource.id)
      }
    })
  },
  async createWidget({ commit, dispatch }, { dashboard, widget }) {
    const { $client } = this
    const tempId = Date.now()
    commit('ADD_WIDGET', { id: tempId, ...widget })
    let widgetData
    try {
      const { data } = await WidgetService($client).create(dashboard.id, widget)
      widgetData = data
    } catch (error) {
      commit('DELETE_WIDGET', tempId)
      throw error
    }
    return await dispatch('handleNewWidgetCreated', {
      tempWidgetId: tempId,
      createdWidget: widgetData,
    })
  },
  async handleNewWidgetCreated(
    { commit, dispatch },
    { tempWidgetId, createdWidget }
  ) {
    commit('UPDATE_WIDGET', { widgetId: tempWidgetId, values: createdWidget })
    dispatch('selectWidget', createdWidget.id)
    await dispatch('fetchNewDataSources', createdWidget.dashboard_id)
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
  async deleteWidget({ dispatch }, widgetId) {
    const { $client } = this
    await WidgetService($client).delete(widgetId)
    dispatch('handleWidgetDeleted', widgetId)
  },
  handleWidgetDeleted({ commit }, widgetId) {
    commit('DELETE_WIDGET', widgetId)
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
    return state.widgets.toSorted((a, b) => a.order - b.order)
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
