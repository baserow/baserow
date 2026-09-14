<template>
  <div class="agent-page">
    <AgentHeader
      :application="application"
      :configuration-open="configurationOpen"
      :running-once="runningOnce"
      @toggle-configuration="configurationOpen = !configurationOpen"
      @open-conversation="openConversation"
      @run-once="runOnce"
    />
    <div class="layout__col-2-2 agent-page__body">
      <AgentConversationList
        class="agent-page__conversation-list"
        :application="application"
      />
      <AgentChat
        class="agent-page__chat"
        :application="application"
        :running-once="runningOnce"
        @run-once="runOnce"
        @open-configuration="openConfiguration"
      />
      <AgentConfigurationPanel
        v-if="configurationOpen"
        v-model:section="configurationSection"
        class="agent-page__configuration"
        :application="application"
        @close="configurationOpen = false"
      />
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useCookie } from '#app'
import { getCookieName } from '@baserow/modules/core/utils/cookie'
import { notifyIf } from '@baserow/modules/core/utils/error'

import AgentHeader from '@baserow_enterprise/components/agentApplication/AgentHeader'
import AgentConversationList from '@baserow_enterprise/components/agentApplication/AgentConversationList'
import AgentChat from '@baserow_enterprise/components/agentApplication/AgentChat'
import AgentConfigurationPanel from '@baserow_enterprise/components/agentApplication/AgentConfigurationPanel'

export default defineComponent({
  name: 'AgentPageContent',
  components: {
    AgentHeader,
    AgentConversationList,
    AgentChat,
    AgentConfigurationPanel,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    application: {
      type: Object,
      required: true,
    },
    autoOpenConfiguration: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup(props) {
    const store = useStore()
    const { $config } = useNuxtApp()

    // Whether the panel is open is remembered in a cookie (not local storage)
    // so the server renders the page in the same state as the client and the
    // panel doesn't pop in after hydration.
    const openCookie = useCookie(
      getCookieName($config, 'agent_configuration_open'),
      { path: '/', maxAge: 60 * 60 * 24 * 365, sameSite: 'lax' }
    )
    const configurationOpen = ref(
      props.autoOpenConfiguration || openCookie.value === 'true'
    )
    watch(configurationOpen, (open) => {
      openCookie.value = open ? 'true' : 'false'
    })
    // Which configuration section is open; kept here so closing and
    // reopening the panel returns to the same place.
    const configurationSection = ref(null)

    const openConfiguration = (section = null) => {
      configurationSection.value = section
      configurationOpen.value = true
    }

    const runningOnce = ref(false)
    const runOnce = async () => {
      if (runningOnce.value) {
        return
      }
      runningOnce.value = true
      try {
        const chat = await store.dispatch('agentApplication/runOnce', {
          applicationId: props.application.id,
        })
        await openConversation(chat.uuid, chat.id)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        runningOnce.value = false
      }
    }

    const openConversation = async (chatUuid, chatId = null) => {
      try {
        await store.dispatch('agentChat/openConversation', {
          applicationId: props.application.id,
          chatUuid,
          chatId,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    return {
      configurationOpen,
      configurationSection,
      openConfiguration,
      runningOnce,
      runOnce,
      openConversation,
    }
  },
})
</script>
