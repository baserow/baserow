<template>
  <div class="agent-page">
    <AgentHeader
      :application="application"
      @new-conversation="newConversation"
      @toggle-configuration="configurationOpen = !configurationOpen"
      @open-conversation="openConversation"
    />
    <div class="layout__col-2-2 agent-page__body">
      <AgentConversationList
        class="agent-page__conversation-list"
        :application="application"
      />
      <AgentChat class="agent-page__chat" :application="application" />
      <AgentConfigurationPanel
        v-if="configurationOpen"
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
    const configurationOpen = ref(false)

    // The page flags an unconfigured (freshly created) agent once its data
    // has been fetched; open the configuration panel automatically then.
    watch(
      () => props.autoOpenConfiguration,
      (value) => {
        if (value) {
          configurationOpen.value = true
        }
      },
      { immediate: true }
    )

    const newConversation = () => {
      store.dispatch('agentChat/newConversation')
    }

    const openConversation = async (chatUuid) => {
      try {
        await store.dispatch('agentChat/openConversation', {
          applicationId: props.application.id,
          chatUuid,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    return {
      configurationOpen,
      newConversation,
      openConversation,
    }
  },
})
</script>
