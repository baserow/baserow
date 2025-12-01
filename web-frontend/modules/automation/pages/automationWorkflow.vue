<template>
  <div class="automation-workflow">
    <AutomationHeader
      v-if="automation"
      :automation="automation"
      @read-only-toggled="handleReadOnlyToggle"
      @debug-toggled="handleDebugToggle"
    />
    <div
      class="layout__col-2-2 automation-workflow__content"
      :class="{
        'automation-workflow__content--loading': workflowLoading,
      }"
    >
      <div v-if="workflowLoading" class="loading"></div>
      <div
        v-else
        class="automation-workflow__editor"
        data-highlight="automation-editor"
      >
        <client-only>
          <WorkflowEditor
            v-model="selectedNodeId"
            :nodes="workflowNodes"
            :is-adding-node="isAddingNode"
            @add-node="handleAddNode"
            @remove-node="handleRemoveNode"
            @replace-node="handleReplaceNode"
            @move-node="handleMoveNode"
            @duplicate-node="handleDuplicateNode"
          />
        </client-only>
      </div>
      <div v-if="activeSidePanel" class="automation-workflow__side-panel">
        <EditorSidePanels
          :active-side-panel="activeSidePanel"
          :data-highlight="activeSidePanelType.guidedTourAttr"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from '@nuxtjs/composition-api'
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor'
import EditorSidePanels from '@baserow/modules/automation/components/workflow/EditorSidePanels'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { StoreItemLookupError } from '@baserow/modules/core/errors'

export default {
  name: 'AutomationWorkflow',
  components: {
    EditorSidePanels,
    AutomationHeader,
    WorkflowEditor,
  },
  provide() {
    return {
      isDev: computed(() => this.isDev),
      workspace: computed(() => this.workspace),
      automation: computed(() => this.automation),
      workflow: computed(() => this.workflow),
      workflowReadOnly: computed({
        get: () => this.workflowReadOnly,
        set: (v) => (this.workflowReadOnly = v),
      }),
      workflowDebug: computed({
        get: () => this.workflowDebug,
        set: (v) => (this.workflowDebug = v),
      }),
    }
  },
  beforeRouteUpdate(to, from, next) {
    this.onRouteChange(to, from, next)
  },
  beforeRouteLeave(to, from, next) {
    this.$store.dispatch('automationWorkflow/unselect')
    this.onRouteChange(to, from, next)
  },
  layout: 'app',
  async asyncData({ store, params, error, app }) {
    const automationId = parseInt(params.automationId)
    const workflowId = parseInt(params.workflowId)
    try {
      const automation = await store.dispatch(
        'application/selectById',
        automationId
      )
      const workspace = await store.dispatch(
        'workspace/selectById',
        automation.workspace.id
      )

      const workflow = await store.dispatch('automationWorkflow/selectById', {
        automation,
        workflowId,
      })

      await store.dispatch('automationHistory/fetchWorkflowHistory', {
        workflowId,
      })

      await store.dispatch('automationWorkflowNode/fetch', {
        workflow,
      })

      const applicationType = app.$registry.get(
        'application',
        AutomationApplicationType.getType()
      )
      await applicationType.loadExtraData(automation)

      return {
        automation,
        workspace,
        workflow,
      }
    } catch (e) {
      error({
        statusCode: 404,
        message: 'Automation workflow not found.',
      })
    }
  },
  data() {
    return {
      isAddingNode: false,
      workflowLoading: false,
      sidePanelWidth: 360,
      workflowReadOnly: false,
      workflowDebug: false,
    }
  },
  computed: {
    isDev() {
      return process.env.NODE_ENV === 'development'
    },
    workflowNodes() {
      if (!this.workflow) {
        return []
      }
      return this.$store.getters['automationWorkflowNode/getNodes'](
        this.workflow
      )
    },
    activeSidePanel() {
      return this.$store.getters['automationWorkflow/getActiveSidePanel']
    },
    activeSidePanelType() {
      return this.activeSidePanel
        ? this.$registry.get('editorSidePanel', this.activeSidePanel)
        : null
    },
    selectedNodeId: {
      get() {
        return this.workflow ? this.workflow.selectedNodeId : null
      },
      set(nodeId) {
        let nodeToSelect = null
        if (nodeId) {
          nodeToSelect = this.$store.getters['automationWorkflowNode/findById'](
            this.workflow,
            nodeId
          )
        }
        this.$store.dispatch('automationWorkflowNode/select', {
          workflow: this.workflow,
          node: nodeToSelect,
        })
      },
    },
  },
  methods: {
    handleReadOnlyToggle(newReadOnlyState) {
      this.workflowReadOnly = newReadOnlyState
    },
    handleDebugToggle(newDebugState) {
      this.workflowDebug = newDebugState
    },
    async handleAddNode({ type, referenceNode, position, output }) {
      try {
        this.isAddingNode = true
        await this.$store.dispatch('automationWorkflowNode/create', {
          workflow: this.workflow,
          type,
          referenceNode,
          position,
          output,
        })
      } catch (err) {
        console.error('Failed to add node:', `${err}`)
        notifyIf(err, 'automation')
      } finally {
        this.isAddingNode = false
      }
    },
    async handleRemoveNode(nodeId) {
      if (!this.workflow) {
        return
      }
      try {
        await this.$store.dispatch('automationWorkflowNode/delete', {
          workflow: this.workflow,
          nodeId: parseInt(nodeId),
        })
      } catch (err) {
        console.error('Failed to delete node:', err)
        notifyIf(err, 'automation')
      }
    },
    async handleReplaceNode({ node, type }) {
      try {
        await this.$store.dispatch('automationWorkflowNode/replace', {
          workflow: this.workflow,
          nodeId: parseInt(node.id),
          newType: type,
        })
      } catch (err) {
        console.error('Failed to replace node:', err)
        notifyIf(err, 'automation')
      }
    },
    onRouteChange(_, from, next) {
      const automation = this.$store.getters['application/get'](
        parseInt(from.params.automationId)
      )
      if (automation) {
        try {
          const workflow = this.$store.getters['automationWorkflow/getById'](
            automation,
            parseInt(from.params.workflowId)
          )

          this.$store.dispatch('automationWorkflowNode/select', {
            workflow,
            node: null,
          })
          this.$store.dispatch('application/forceUpdate', {
            application: automation,
            data: { _loadedOnce: false },
          })
        } catch (e) {
          if (!(e instanceof StoreItemLookupError)) {
            throw e
          }
        }
      }
      next()
    },
    async handleMoveNode(moveData) {
      const movedNodeId =
        this.$store.getters['automationWorkflowNode/getDraggingNodeId']

      this.$store.dispatch('automationWorkflowNode/setDraggingNodeId', null)

      if (!movedNodeId) {
        return
      }
      try {
        await this.$store.dispatch('automationWorkflowNode/move', {
          workflow: this.workflow,
          moveData: {
            movedNodeId,
            ...moveData,
          },
        })
      } catch (err) {
        console.error('Failed to move node:', err)
        notifyIf(err, 'automation')
      }
    },
    async handleDuplicateNode(nodeId) {
      await this.$store.dispatch('automationWorkflowNode/duplicate', {
        workflow: this.workflow,
        nodeId,
      })
    },
  },
}
</script>
