<template>
  <header class="layout__col-2-1 header header--space-between">
    <ul class="header__filter">
      <li
        v-if="
          $hasPermission(
            'application.update',
            automation,
            automation.workspace.id
          )
        "
        class="header__filter-item"
      >
        <a
          data-item-type="settings"
          class="header__filter-link"
          @click="openSettingsModal"
          ><i class="header__filter-icon iconoir-settings"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.settingsBtn')
          }}</span>
        </a>
      </li>
      <li class="header__filter-item">
        <a
          data-item-type="history"
          data-highlight="automation-history"
          class="header__filter-link"
          :class="{ 'active--primary': activeSidePanel === 'history' }"
          @click="historyClick()"
          ><i class="header__filter-icon baserow-icon-history"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.historyBtn')
          }}</span>
        </a>
      </li>
      <li class="header__filter-item">
        <a
          data-highlight="automation-docs"
          class="header__filter-link"
          target="_blank"
          href="https://baserow.io/user-docs/workflow-automation"
          ><i class="header__filter-icon iconoir-help-circle"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.docsBtn')
          }}</span>
        </a>
      </li>
      <li v-if="isDev" class="header__filter-item">
        <a
          data-item-type="debug"
          class="header__filter-link"
          :class="{
            'active active--purple': debug,
          }"
          @click="debugClick()"
          ><i class="header__filter-icon iconoir-hammer"></i>
          <span class="header__filter-name">{{
            debug ? 'Debug off' : 'Debug on'
          }}</span>
        </a>
      </li>
    </ul>

    <div class="header__right">
      <span class="header__switch-container">
        <template v-if="!publishedOn">
          <Badge color="cyan" rounded size="small">{{
            $t('automationHeader.switchLabelDraft')
          }}</Badge>
        </template>
        <template v-else>
          <Badge v-if="isDisabled" color="red" rounded size="small">{{
            $t('automationHeader.switchLabelDisabled')
          }}</Badge>
          <Badge v-else-if="isPaused" color="red" rounded size="small">{{
            $t('automationHeader.switchLabelPaused')
          }}</Badge>
          <Badge v-else color="green" rounded size="small">{{
            $t('automationHeader.switchLabelLive')
          }}</Badge>
        </template>
        <SwitchInput
          small
          data-highlight="automation-workflow-state"
          :value="statusSwitch"
          :disabled="isDisabled || !publishedOn"
          @input="toggleStatusSwitch"
        ></SwitchInput>
      </span>

      <div class="header__buttons header__buttons--with-separator">
        <ClientOnly>
          <div v-if="publishedOn" class="automation-header__last-published">
            {{ $t('automationHeader.lastPublished') }}: {{ publishedOn }}
          </div>
        </ClientOnly>
        <Button
          :icon="testRunEnabled ? 'iconoir-cancel' : 'iconoir-play'"
          type="secondary"
          data-highlight="automation-test-run"
          :disabled="testRunDisabled"
          @click="toggleTestRun"
          >{{
            testRunEnabled
              ? $t('automationHeader.stopTestRun')
              : $t('automationHeader.startTestRun')
          }}</Button
        >
        <Button
          data-highlight="automation-publish"
          :loading="isPublishing"
          :disabled="isPublishing || !canPublishWorkflow"
          @click="publishWorkflow()"
        >
          {{ $t('automationHeader.publishBtn') }}
        </Button>
      </div>
    </div>
    <AutomationSettingsModal
      ref="automationSettingsModal"
      :automation="automation"
    />
  </header>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'
import { defineComponent, ref, computed } from 'vue'
import { useStore, inject, useContext } from '@nuxtjs/composition-api'
import { HistoryEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { WORKFLOW_STATES } from '@baserow/modules/automation/components/enums'

import NodeGraphHandler from '@baserow/modules/automation/utils/nodeGraphHandler'
import AutomationSettingsModal from '@baserow/modules/automation/components/settings/AutomationSettingsModal'

export default defineComponent({
  name: 'AutomationHeader',
  components: { AutomationSettingsModal },
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },
  setup(props, { emit }) {
    const store = useStore()
    const { app } = useContext()
    const isDev = inject('isDev')

    const debug = ref(false)
    const isPublishing = ref(false)

    const workflow = inject('workflow')

    const selectedWorkflow = computed(() => {
      if (!props.automation) return null
      try {
        return store.getters['automationWorkflow/getSelected']
      } catch (error) {
        return null
      }
    })

    const testRunDisabled = computed(() => {
      return !new NodeGraphHandler(workflow.value).hasNodes()
    })

    const testRunEnabled = computed(() => {
      return (
        moment(workflow.value?.allow_test_run_until).isAfter() ||
        Number.isInteger(workflow.value?.simulate_until_node_id)
      )
    })

    const hasActionNode = computed(() => {
      if (!workflow.value?.nodes) {
        return false
      }

      const _nodes = workflow.value.nodes.filter((node) => {
        const nodeType = app.$registry.get('node', node.type)
        const isInError = nodeType.isInError({ service: node.service })
        return nodeType.isWorkflowAction === true && !isInError
      })

      return _nodes.length > 0
    })

    const canPublishWorkflow = computed(() => {
      return hasActionNode.value && !isPublishing.value
    })

    const publishedOn = computed(() => {
      if (!selectedWorkflow.value?.published_on || isPublishing.value) {
        return null
      }

      return moment
        .utc(selectedWorkflow.value.published_on)
        .tz(getUserTimeZone())
        .format('MMM D, YYYY HH:mm:ss')
    })

    const statusSwitch = computed(() => {
      return workflow.value?.state === WORKFLOW_STATES.LIVE
    })

    const isPaused = computed(() => {
      return (
        publishedOn.value && workflow.value?.state === WORKFLOW_STATES.PAUSED
      )
    })

    const isDisabled = computed(() => {
      return workflow.value?.state === WORKFLOW_STATES.DISABLED
    })

    const activeSidePanel = computed(() => {
      return store.getters['automationWorkflow/getActiveSidePanel']
    })

    const toggleTestRun = async () => {
      try {
        await store.dispatch('automationWorkflow/testRun', {
          workflow: workflow.value,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }
    }

    const toggleStatusSwitch = async () => {
      const newValue =
        workflow.value.state === WORKFLOW_STATES.PAUSED
          ? WORKFLOW_STATES.LIVE
          : WORKFLOW_STATES.PAUSED

      try {
        await store.dispatch('automationWorkflow/update', {
          automation: props.automation,
          workflow: workflow.value,
          values: {
            state: newValue,
          },
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }
    }

    const historyClick = () => {
      let sidePanelType = HistoryEditorSidePanelType.getType()

      // Clicking the History button should toggle the active state
      if (activeSidePanel.value === sidePanelType) {
        sidePanelType = null
      }

      store.dispatch('automationWorkflow/setActiveSidePanel', sidePanelType)
    }

    const debugClick = () => {
      debug.value = !debug.value
      emit('debug-toggled', debug.value)
    }

    const publishWorkflow = async () => {
      isPublishing.value = true

      try {
        await store.dispatch('automationWorkflow/publishWorkflow', {
          workflow: workflow.value,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }
      isPublishing.value = false
    }

    const automationSettingsModal = ref(null)
    const openSettingsModal = () => {
      automationSettingsModal.value.show()
    }

    return {
      isDev,
      debug,
      statusSwitch,
      debugClick,
      historyClick,
      toggleTestRun,
      testRunEnabled,
      publishWorkflow,
      toggleStatusSwitch,
      canPublishWorkflow,
      publishedOn,
      isPublishing,
      isPaused,
      isDisabled,
      selectedWorkflow,
      workflow,
      activeSidePanel,
      testRunDisabled,
      openSettingsModal,
      automationSettingsModal,
    }
  },
})
</script>
