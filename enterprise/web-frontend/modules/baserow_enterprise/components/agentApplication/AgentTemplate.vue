<template>
  <div class="agent-page">
    <AgentHeader
      :application="application"
      :configuration-open="configurationOpen"
      :loading="loading"
      @toggle-configuration="configurationOpen = !configurationOpen"
    />
    <div class="layout__col-2-2 agent-page__body">
      <AgentConversationList
        class="agent-page__conversation-list"
        :application="application"
        :page-loading="loading"
      />
      <AgentChat
        class="agent-page__chat"
        :application="application"
        :loading="loading"
        @open-configuration="openConfiguration"
      />
      <AgentConfigurationPanel
        v-if="configurationOpen"
        v-model:section="configurationSection"
        class="agent-page__configuration"
        :application="application"
        :loading="loading"
        @close="configurationOpen = false"
      />
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, computed, watch } from 'vue'
import { useStore } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  STORE_PREFIX_KEY,
  TEMPLATE_KEY,
} from '@baserow_enterprise/composables/useAgentContext'
import AgentHeader from '@baserow_enterprise/components/agentApplication/AgentHeader'
import AgentConversationList from '@baserow_enterprise/components/agentApplication/AgentConversationList'
import AgentChat from '@baserow_enterprise/components/agentApplication/AgentChat'
import AgentConfigurationPanel from '@baserow_enterprise/components/agentApplication/AgentConfigurationPanel'

const STORE_PREFIX = 'template/'

/**
 * The agent page as a template preview: the example conversations, the first
 * one opened, and the configuration panel, all read-only. The page components
 * are the real ones; they read the `template/` stores and treat every
 * permission as denied, so nothing can be sent to or changed on a template.
 */
export default defineComponent({
  name: 'AgentTemplate',
  components: {
    AgentHeader,
    AgentConversationList,
    AgentChat,
    AgentConfigurationPanel,
  },
  provide: {
    [STORE_PREFIX_KEY]: STORE_PREFIX,
    [TEMPLATE_KEY]: true,
  },
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const application = computed(() => props.pageValue.application)
    const loading = ref(true)
    const configurationOpen = ref(true)
    const configurationSection = ref(null)
    const openConfiguration = (section = null) => {
      configurationSection.value = section
      configurationOpen.value = true
    }

    const fetch = async () => {
      const applicationId = application.value.id
      loading.value = true
      configurationSection.value = null
      store.dispatch(`${STORE_PREFIX}agentChat/newConversation`)
      store.dispatch(`${STORE_PREFIX}agentHistory/clear`)
      try {
        await Promise.all([
          store.dispatch(`${STORE_PREFIX}agentApplication/fetch`, {
            applicationId,
          }),
          store.dispatch(`${STORE_PREFIX}agentApplication/fetchTriggers`, {
            applicationId,
          }),
          store.dispatch(`${STORE_PREFIX}agentApplication/fetchTools`, {
            applicationId,
          }),
          store
            .dispatch(`${STORE_PREFIX}agentApplication/fetchChannels`, {
              applicationId,
            })
            .catch(() => {}),
          store
            .dispatch(
              `${STORE_PREFIX}agentApplication/fetchWorkspaceToolCatalog`,
              { applicationId }
            )
            .catch(() => {}),
          store.dispatch(`${STORE_PREFIX}agentHistory/fetch`, {
            applicationId,
          }),
        ])
        const [first] = store.getters[`${STORE_PREFIX}agentHistory/getChats`]
        if (first && application.value.id === applicationId) {
          await store.dispatch(`${STORE_PREFIX}agentChat/openConversation`, {
            applicationId,
            chatUuid: first.uuid,
          })
        }
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        if (application.value.id === applicationId) {
          loading.value = false
        }
      }
    }
    watch(() => application.value.id, fetch, { immediate: true })

    return {
      application,
      loading,
      configurationOpen,
      configurationSection,
      openConfiguration,
    }
  },
})
</script>
