<template>
  <div>
    <SidebarApplication
      ref="sidebarApplication"
      :workspace="workspace"
      :application="application"
      :highlighted="isAppSelected(application)"
      @selected="selected"
    >
      <template v-if="isAppSelected(application)" #body>
        <ul class="tree__subs">
          <SidebarItemAutomation
            v-for="workflow in orderedWorkflows"
            :key="workflow.id"
            v-sortable="{
              id: workflow.id,
              update: orderWorkflows,
              marginTop: -1.5,
              enabled: $hasPermission(
                'automation.workflow.order',
                application,
                application.workspace.id
              ),
            }"
            :automation="application"
            :workflow="workflow"
          ></SidebarItemAutomation>
        </ul>

        <a
          v-if="
            $hasPermission(
              'automation.workflow.create',
              application,
              application.workspace.id
            )
          "
          class="tree__sub-add"
          @click="$refs.createAutomationWorkflowModal.show()"
        >
          <i class="tree__sub-add-icon iconoir-plus"></i>
          {{ $t('sidebarComponentAutomation.createAutomationWorkflow') }}
        </a>
        <CreateAutomationWorkflowModal
          ref="createAutomationWorkflowModal"
          :automation="application"
          :workspace="application.workspace"
        ></CreateAutomationWorkflowModal>
      </template>
    </SidebarApplication>
  </div>
</template>

<script>
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import SidebarItemAutomation from '@baserow/modules/automation/components/sidebar/SidebarItemAutomation'
import CreateAutomationWorkflowModal from '@baserow/modules/automation/components/workflow/CreateAutomationWorkflowModal'

import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'SidebarComponentAutomation',
  components: {
    SidebarApplication,
    SidebarItemAutomation,
    CreateAutomationWorkflowModal,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      isAppSelected: 'application/isSelected',
      getOrderedWorkflows: 'automationWorkflow/getOrderedWorkflows',
    }),
    orderedWorkflows() {
      return this.getOrderedWorkflows(this.application)
    },
  },
  methods: {
    async selected(application) {
      try {
        this.$store.dispatch('application/select', application)
        await this.$nuxt.$router.push({
          name: 'automation-application',
          params: {
            automationId: this.application.id,
          },
        })
      } catch (error) {
        if (error.name !== 'NavigationDuplicated') {
          notifyIf(error, 'workspace')
        }
      }
    },
    orderWorkflows(order, oldOrder) {
      try {
        this.$store.dispatch('automationWorkflow/order', {
          automation: this.application,
          order,
          oldOrder,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }
    },
  },
}
</script>
