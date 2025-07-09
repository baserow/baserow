<template>
  <header class="layout__col-2-1 header header--space-between">
    <ul class="header__filter">
      <li v-if="isDev" class="header__filter-item">
        <a data-item-type="settings" class="header__filter-link"
          ><i class="header__filter-icon iconoir-settings"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.settingsBtn')
          }}</span>
        </a>
      </li>

      <li v-if="isDev" class="header__filter-item">
        <a
          data-item-type="history"
          class="header__filter-link"
          @click="historyClick()"
          ><i class="header__filter-icon baserow-icon-history"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.historyBtn')
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
          <Badge v-if="workflow?.disabled" color="red" rounded size="small">{{
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
          :value="statusSwitch"
          :disabled="workflow?.disabled || !publishedOn"
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
          @click="toggleTestRun"
          >{{
            testRunEnabled
              ? $t('automationHeader.stopTestRun')
              : $t('automationHeader.startTestRun')
          }}</Button
        >
        <Button
          :loading="isPublishing"
          :disabled="isPublishing || !canPublishWorkflow"
          @click="publishWorkflow()"
        >
          {{ $t('automationHeader.publishBtn') }}
        </Button>
      </div>
    </div>
  </header>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'
import { defineComponent, ref, computed } from 'vue'
import { useStore, inject, useContext } from '@nuxtjs/composition-api'
import { HistoryEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default defineComponent({
  name: 'AutomationHeader',
  components: {},
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

    const testRunEnabled = computed(() => {
      return moment(workflow.value?.allow_test_run_until).isAfter()
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
      return (publishedOn.value && !workflow.value?.paused) || false
    })

    const isPaused = computed(() => {
      return publishedOn.value && workflow.value?.paused
    })

    const toggleTestRun = async () => {
      try {
        await store.dispatch('automationWorkflow/toggleTestRun', {
          workflow: workflow.value,
          allowTestRun: !testRunEnabled.value,
        })
      } catch (error) {
        notifyIf(error, 'automationWorkflow')
      }
    }

    const toggleStatusSwitch = async () => {
      const oldValue = workflow.value.paused
      workflow.value.paused = !oldValue

      try {
        await store.dispatch('automationWorkflow/update', {
          automation: props.automation,
          workflow: workflow.value,
          values: {
            paused: workflow.value.paused,
          },
        })
      } catch (error) {
        workflow.value.paused = oldValue
        notifyIf(error, 'automationWorkflow')
      }
    }

    const historyClick = () => {
      store.dispatch(
        'automationWorkflow/setActiveSidePanel',
        HistoryEditorSidePanelType.getType()
      )
    }

    const publishWorkflow = async () => {
      isPublishing.value = true

      const originalPaused = workflow.value.paused
      const originalDisabled = workflow.value.disabled

      try {
        workflow.value.paused = false
        workflow.value.disabled = false
        await store.dispatch('automationWorkflow/publishWorkflow', {
          workflow: workflow.value,
        })
      } catch (error) {
        workflow.value.paused = originalPaused
        workflow.value.disabled = originalDisabled
        notifyIf(error, 'automationWorkflow')
      }
      isPublishing.value = false
    }

    return {
      isDev,
      statusSwitch,
      historyClick,
      toggleTestRun,
      testRunEnabled,
      publishWorkflow,
      toggleStatusSwitch,
      canPublishWorkflow,
      publishedOn,
      isPublishing,
      isPaused,
      selectedWorkflow,
      workflow,
    }
  },
})
</script>
