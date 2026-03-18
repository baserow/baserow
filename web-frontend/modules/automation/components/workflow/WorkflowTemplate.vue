<template>
  <AutomationWorkflowContent
    v-if="!loading && workspace && workflow && automation"
    :workspace="workspace"
    :automation="automation"
    :workflow="workflow"
    :loading="loading"
  />
  <PageSkeleton v-else />
</template>

<script>
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import AutomationWorkflowContent from '@baserow/modules/automation/components/AutomationWorkflowContent'
import PageSkeleton from '@baserow/modules/core/components/template/PageSkeleton'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'

export default {
  name: 'WorkflowTemplate',
  components: { AutomationWorkflowContent, PageSkeleton },
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      workspace: null,
      automation: null,
      workflow: null,
      loading: true,
    }
  },
  watch: {
    'pageValue.workflow.id': {
      handler() {
        this.loadData()
      },
      immediate: true,
    },
  },
  unmounted() {
    // Restore the current application to the selected application if any
    this.$store.dispatch('userSourceUser/setCurrentApplication', {
      application: this.$store.getters['application/getSelected'],
    })
  },
  methods: {
    async loadData() {
      this.loading = true

      try {
        const automation = this.pageValue.automation
        const workflow = await this.$store.dispatch(
          'automationWorkflow/selectById',
          {
            automation,
            workflowId: this.pageValue.workflow.id,
          }
        )

        const automationApplicationType = this.$registry.get(
          'application',
          AutomationApplicationType.getType()
        )

        await automationApplicationType.loadExtraData(automation)

        await this.$store.dispatch('automationWorkflowNode/fetch', {
          workflow,
        })

        this.automation = automation
        this.workflow = workflow
        this.workspace = automation.workspace
      } catch (e) {
        // In case of a network error we want to fail hard.
        if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
          throw e
        }
      }

      this.loading = false
    },
  },
}
</script>
