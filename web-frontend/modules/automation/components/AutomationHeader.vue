<template>
  <header class="layout__col-2-1 header header--space-between">
    <ul class="header__filter">
      <li class="header__filter-item">
        <a data-item-type="settings" class="header__filter-link"
          ><i class="header__filter-icon iconoir-settings"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.settingsBtn')
          }}</span>
        </a>
      </li>

      <li class="header__filter-item">
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
        <Badge v-if="publishedOn" color="green" rounded size="small">{{
          $t('automationHeader.switchLabelLive')
        }}</Badge>
        <Badge v-else color="cyan" rounded size="small">{{
          $t('automationHeader.switchLabelDraft')
        }}</Badge>
        <SwitchInput
          small
          :value="switchValue"
          @input="switchValue = !switchValue"
        ></SwitchInput>
      </span>

      <span
        v-if="isDevEnvironment"
        class="header__switch-container u-margin-left-2"
      >
        <Badge color="yellow" rounded size="small">{{
          $t('automationHeader.readOnlyLabel')
        }}</Badge>
        <SwitchInput
          small
          :value="readOnlySwitchValue"
          @input="toggleReadOnly"
        ></SwitchInput>
      </span>

      <div class="header__buttons header__buttons--with-separator">
        <div v-if="publishedOn" class="automation-header__last-published">
          Last published: {{ publishedOn }}
        </div>
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
          v-tooltip="
            !canPublishWorkflow ? $t('automationHeader.cantPublishTooltip') : ''
          "
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
  emits: ['read-only-toggled'],
  setup(props, { emit }) {
    const store = useStore()
    const { app } = useContext()

    const switchValue = ref(false)
    const readOnlySwitchValue = ref(false)
    const isPublishing = ref(false)

    // Check if in development environment
    const isDevEnvironment = computed(
      () => process.env.NODE_ENV === 'development'
    )

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

    const hasTriggerNode = computed(() => {
      if (!workflow.value?.nodes) {
        return false
      }

      const _nodes = workflow.value.nodes.filter((node) => {
        const nodeType = app.$registry.get('node', node.type)
        return nodeType.isTrigger === true
      })

      return _nodes.length === 1
    })

    const hasActionNode = computed(() => {
      if (!workflow.value?.nodes) {
        return false
      }

      const _nodes = workflow.value.nodes.filter((node) => {
        const nodeType = app.$registry.get('node', node.type)
        return nodeType.isWorkflowAction === true
      })

      return _nodes.length > 0
    })

    const canPublishWorkflow = computed(() => {
      return hasTriggerNode.value && hasActionNode.value && !isPublishing.value
    })

    const publishedOn = computed(() => {
      if (!selectedWorkflow.value?.published_on || isPublishing.value) {
        return null
      }

      return moment
        .utc(selectedWorkflow.value.published_on)
        .tz(moment.tz.guess())
        .format('MMM D, YYYY HH:MM:SS')
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

    const toggleReadOnly = () => {
      readOnlySwitchValue.value = !readOnlySwitchValue.value
      emit('read-only-toggled', readOnlySwitchValue.value)
    }

    const historyClick = () => {
      store.dispatch(
        'automationWorkflow/setActiveSidePanel',
        HistoryEditorSidePanelType.getType()
      )
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

    return {
      switchValue,
      readOnlySwitchValue,
      toggleReadOnly,
      historyClick,
      toggleTestRun,
      testRunEnabled,
      isDevEnvironment,
      publishWorkflow,
      canPublishWorkflow,
      publishedOn,
      isPublishing,
      selectedWorkflow,
      // temp
      workflow,
    }
  },
})
</script>
