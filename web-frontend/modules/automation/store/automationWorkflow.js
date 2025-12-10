import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import AutomationWorkflowService from '@baserow/modules/automation/services/workflow'
import { generateHash } from '@baserow/modules/core/utils/hashing'
import { AUTOMATION_ACTION_SCOPES } from '@baserow/modules/automation/utils/undoRedoConstants'

export function populateAutomationWorkflow(workflow) {
  return {
    ...workflow,
    nodes: [],
    orderedNodes: [],
    nodeMap: {},
    selectedNodeId: null,
    _: {
      selected: false,
    },
  }
}

const state = {
  // Holds the value of which workflow is currently selected
  selected: {},
  // A job object that tracks the progress of a workflow duplication currently running
  duplicateJob: null,
  // Which side panel is currently active in this workflow? The options are:
  // `null` (side panel is closed), `history` (view workflow run history) and
  // `node` (trigger and action node edit forms).
  activeSidePanel: null,
}

const mutations = {
  ADD_ITEM(state, { automation, workflow }) {
    automation.workflows.push(populateAutomationWorkflow(workflow))
  },
  UPDATE_ITEM(state, { workflow, values }) {
    Object.assign(workflow, values)
  },
  DELETE_ITEM(state, { automation, id }) {
    const index = automation.workflows.findIndex((item) => item.id === id)
    if (index > -1) {
      automation.workflows.splice(index, 1)
    }
  },
  SET_SELECTED(state, { automation, workflow }) {
    Object.values(automation.workflows).forEach((item) => {
      item._.selected = false
    })
    workflow._.selected = true
    state.selected = workflow
  },
  UNSELECT(state) {
    if (state.selected?._?.selected) {
      state.selected._.selected = false
    }
    state.selected = {}
  },
  SET_DUPLICATE_JOB(state, job) {
    state.duplicateJob = job
  },
  ORDER_WORKFLOWS(state, { automation, order, isHashed = false }) {
    automation.workflows.forEach((workflow) => {
      const workflowId = isHashed ? generateHash(workflow.id) : workflow.id
      const index = order.findIndex((value) => value === workflowId)
      workflow.order = index === -1 ? 0 : index + 1
    })
  },
  SET_ACTIVE_SIDE_PANEL(state, sidePanelType) {
    state.activeSidePanel = sidePanelType
  },
}

const actions = {
  forceUpdate({ commit }, { workflow, values }) {
    commit('UPDATE_ITEM', { workflow, values })
  },
  forceCreate({ commit }, { automation, workflow }) {
    commit('ADD_ITEM', { automation, workflow })
  },
  selectById({ commit, dispatch, getters }, { automation, workflowId }) {
    const type = AutomationApplicationType.getType()

    // Check if the selected application is an automation
    if (automation.type !== type) {
      throw new StoreItemLookupError(
        `The application doesn't have the required ${type} type.`
      )
    }

    // Check if the provided workflowId is found in the selected automation.
    const workflow = getters.getById(automation, workflowId)

    dispatch(
      'undoRedo/updateCurrentScopeSet',
      AUTOMATION_ACTION_SCOPES.workflow(workflow.id),
      { root: true }
    )

    commit('SET_SELECTED', { automation, workflow })

    return workflow
  },
  unselect({ commit, dispatch }) {
    commit('UNSELECT')
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      AUTOMATION_ACTION_SCOPES.workflow(null),
      { root: true }
    )
  },
  async forceDelete({ commit }, { automation, workflow }) {
    if (workflow._?.selected) {
      // Redirect back to the dashboard because the workflow doesn't exist anymore.
      await this.$router.push({ name: 'dashboard' })
      commit('UNSELECT')
    }

    commit('DELETE_ITEM', { automation, id: workflow.id })
  },
  async create({ commit, dispatch }, { automation, name }) {
    const { data: workflow } = await AutomationWorkflowService(
      this.$client
    ).create(automation.id, name)

    commit('ADD_ITEM', { automation, workflow })

    await dispatch('selectById', { automation, workflowId: workflow.id })

    return workflow
  },
  async fetchById({ getters, commit, dispatch }, { automation, workflowId }) {
    const { data } = await AutomationWorkflowService(this.$client).read(
      workflowId
    )
    const workflow = getters.getById(automation, workflowId)
    dispatch('forceUpdate', {
      workflow,
      values: {
        ...data,
        nodes: workflow.nodes,
        nodeMap: workflow.nodeMap,
      },
    })
    return data
  },
  async update({ dispatch }, { automation, workflow, values }) {
    const { data } = await AutomationWorkflowService(this.$client).update(
      workflow.id,
      values
    )

    const update = Object.keys(values).reduce((result, key) => {
      result[key] = data[key]
      return result
    }, {})

    await dispatch('forceUpdate', { workflow, values: update })
  },
  async delete({ dispatch }, { automation, workflow }) {
    await AutomationWorkflowService(this.$client).delete(workflow.id)

    await dispatch('forceDelete', { automation, workflow })
  },
  async order(
    { commit, getters },
    { automation, order, oldOrder, isHashed = false }
  ) {
    commit('ORDER_WORKFLOWS', { automation, order, isHashed })

    try {
      await AutomationWorkflowService(this.$client).order(automation.id, order)
    } catch (error) {
      commit('ORDER_WORKFLOWS', { automation, order: oldOrder, isHashed })
      throw error
    }
  },
  async duplicate({ commit, dispatch }, { workflow }) {
    const { data: job } = await AutomationWorkflowService(
      this.$client
    ).duplicate(workflow.id)

    await dispatch('job/create', job, { root: true })

    commit('SET_DUPLICATE_JOB', job)
  },
  setActiveSidePanel({ commit }, sidePanelType) {
    commit('SET_ACTIVE_SIDE_PANEL', sidePanelType)
  },
  async testRun({ dispatch }, { workflow }) {
    await AutomationWorkflowService(this.$client).testRun(workflow.id)
  },
  async publishWorkflow({ dispatch }, { workflow }) {
    await AutomationWorkflowService(this.$client).publish(workflow.id)
  },
}

const getters = {
  getWorkflows: (state) => (automation) => {
    return automation?.workflows ? [...automation.workflows] : []
  },
  getOrderedWorkflows: (state, getters) => (automation) => {
    return getters.getWorkflows(automation).sort((a, b) => a.order - b.order)
  },
  getById: (state, getters) => (automation, workflowId) => {
    const index = getters
      .getWorkflows(automation)
      .findIndex((item) => item.id === workflowId)

    if (index === -1) {
      throw new StoreItemLookupError(
        'The workflow was not found in the selected automation.'
      )
    }

    return getters.getWorkflows(automation)[index]
  },
  getSelected(state) {
    return state.selected
  },
  getDuplicateJob(state) {
    return state.duplicateJob
  },
  getActiveSidePanel(state) {
    return state.activeSidePanel
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
