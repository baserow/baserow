<template>
  <div v-if="oauthEnabled" class="mcp-oauth-connections">
    <h3 class="mcp-oauth-connections__title">
      {{ $t('mcpOAuthConnections.title') }}
    </h3>
    <p class="mcp-oauth-connections__description">
      {{ $t('mcpOAuthConnections.description') }}
    </p>
    <div class="mcp-oauth-connections__url margin-bottom-1">
      <div class="mcp-oauth-connections__url-box" data-test="mcp-oauth-url">
        {{ mcpUrl }}
      </div>
      <a
        v-tooltip="$t('mcpOAuthConnections.copyURL')"
        class="mcp-oauth-connections__url-copy"
        @click="copyUrl"
      >
        <i class="iconoir-copy" />
        <Copied ref="copied"></Copied>
      </a>
    </div>
    <Tabs header-no-padding content-no-x-padding>
      <Tab title="Claude">
        <MarkdownIt
          class="mcp-oauth-connections__instructions"
          :content="$t('mcpOAuthConnections.claudeInstructions')"
        ></MarkdownIt>
      </Tab>
      <Tab title="Claude Code">
        <MarkdownIt
          class="mcp-oauth-connections__instructions margin-bottom-1"
          :content="$t('mcpOAuthConnections.claudeCodeInstructions')"
        ></MarkdownIt>
        <pre><code class="mcp-oauth-connections__code">claude mcp add --transport http baserow {{ mcpUrl }}</code></pre>
      </Tab>
      <Tab title="ChatGPT">
        <MarkdownIt
          class="mcp-oauth-connections__instructions"
          :content="$t('mcpOAuthConnections.chatGptInstructions')"
        ></MarkdownIt>
      </Tab>
      <Tab title="Cursor">
        <MarkdownIt
          class="mcp-oauth-connections__instructions margin-bottom-1"
          :content="$t('mcpOAuthConnections.cursorInstructions')"
        ></MarkdownIt>
        <pre><code class="mcp-oauth-connections__code">{
  "mcpServers": {
    "baserow": {
      "url": "{{ mcpUrl }}"
    }
  }
}</code></pre>
      </Tab>
    </Tabs>
    <h3 class="mcp-oauth-connections__title">
      {{ $t('mcpOAuthConnections.connectedApps') }}
    </h3>
    <p
      v-if="!connections.length"
      class="mcp-oauth-connections__empty"
      data-test="mcp-oauth-empty"
    >
      {{ $t('mcpOAuthConnections.noConnections') }}
    </p>
    <div
      v-for="connection in connections"
      :key="connection.id"
      class="mcp-oauth-connections__item"
      :data-test="`mcp-oauth-connection-${connection.id}`"
    >
      <div class="mcp-oauth-connections__avatar">
        {{ initial(connection.client_name) }}
      </div>
      <div class="mcp-oauth-connections__info">
        <div class="mcp-oauth-connections__name">
          <span class="mcp-oauth-connections__client">{{
            connection.client_name
          }}</span>
          <Badge
            v-if="connection.verified"
            size="small"
            data-test="mcp-oauth-published"
            >{{
              $t('mcpOAuthConnections.publishedBy', {
                host: connection.verified_host,
              })
            }}</Badge
          >
        </div>
        <div class="mcp-oauth-connections__meta">
          {{ connection.workspace_name }} ·
          {{ toolCount(connection.tool_count) }} ·
          {{ connectedOn(connection.created) }}
        </div>
      </div>
      <Button
        type="secondary"
        size="small"
        :loading="disconnecting === connection.id"
        :disabled="disconnecting === connection.id"
        data-test="mcp-oauth-disconnect"
        @click="disconnect(connection)"
        >{{
          confirming === connection.id
            ? $t('mcpOAuthConnections.confirmDisconnect')
            : $t('mcpOAuthConnections.disconnect')
        }}</Button
      >
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import moment from '@baserow/modules/core/moment'
import MCPOAuthService from '@baserow/modules/core/services/mcpOAuth'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

const emit = defineEmits(['loaded'])

const { $client } = useNuxtApp()
const { t } = useI18n()

const oauthEnabled = ref(false)
const mcpUrl = ref('')
const connections = ref([])
const confirming = ref(null)
const disconnecting = ref(null)
const copied = ref(null)

onMounted(async () => {
  try {
    const { data } = await MCPOAuthService($client).fetchConnections()
    oauthEnabled.value = data.oauth_enabled
    mcpUrl.value = data.mcp_url
    connections.value = data.connections
  } catch (error) {
    notifyIf(error)
  }
  emit('loaded', oauthEnabled.value)
})

function initial(name) {
  return (name || '').trim().charAt(0).toUpperCase()
}

function toolCount(count) {
  return t('mcpOAuthConnections.tools', { count })
}

function connectedOn(created) {
  return t('mcpOAuthConnections.connectedOn', {
    date: moment.utc(created).local().format('L'),
  })
}

function copyUrl() {
  copyToClipboard(mcpUrl.value)
  copied.value.show()
}

/**
 * The first click asks for confirmation, the second one deletes the grant,
 * which also revokes the app's tokens.
 */
async function disconnect(connection) {
  if (confirming.value !== connection.id) {
    confirming.value = connection.id
    return
  }
  disconnecting.value = connection.id
  try {
    await MCPOAuthService($client).disconnect(connection.id)
    connections.value = connections.value.filter((c) => c.id !== connection.id)
  } catch (error) {
    notifyIf(error)
  }
  confirming.value = null
  disconnecting.value = null
}
</script>
