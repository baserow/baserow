<template>
  <div class="auth__wrapper mcp-authorize">
    <div class="auth__logo">
      <Logo />
    </div>
    <div class="auth__head auth__head-title">
      <h1>{{ $t('mcpAuthorize.title') }}</h1>
    </div>
    <Error :error="error" />
    <div v-if="consent" class="mcp-authorize__body">
      <p class="mcp-authorize__client">
        {{ $t('mcpAuthorize.wants', { client: consent.client_name }) }}
      </p>
      <p class="mcp-authorize__redirect">
        {{ $t('mcpAuthorize.redirect', { host: consent.redirect_host }) }}
      </p>
      <FormGroup :label="$t('mcpAuthorize.workspace')" required>
        <p
          v-if="!consent.workspaces.length"
          class="mcp-authorize__empty"
          data-test="mcp-authorize-no-workspaces"
        >
          {{ $t('mcpAuthorize.noWorkspaces') }}
        </p>
        <Dropdown v-else v-model="workspaceId" :show-search="false">
          <DropdownItem
            v-for="workspace in consent.workspaces"
            :key="workspace.id"
            :name="workspace.name"
            :value="workspace.id"
          />
        </Dropdown>
      </FormGroup>
      <FormGroup :label="$t('mcpAuthorize.tools')" required>
        <p v-if="!consent.tools.length" class="mcp-authorize__empty">
          {{ $t('mcpAuthorize.noTools') }}
        </p>
        <div
          v-for="group in toolGroups"
          :key="group.key"
          class="mcp-authorize__tool-group"
          :data-test="`mcp-authorize-tools-${group.key}`"
        >
          <div class="mcp-authorize__tool-group-title">
            {{ $t(group.label) }}
          </div>
          <Checkbox
            v-for="tool in group.tools"
            :key="tool.name"
            v-model="ticked[tool.name]"
            class="mcp-authorize__tool"
            :data-test="`mcp-authorize-tool-${tool.name}`"
          >
            {{ tool.title }}
            <span v-if="tool.destructive" class="mcp-authorize__tool-hint">{{
              $t('mcpAuthorize.destructiveHint')
            }}</span>
          </Checkbox>
        </div>
      </FormGroup>
      <div class="mcp-authorize__actions">
        <Button
          type="secondary"
          :disabled="loading"
          data-test="mcp-authorize-deny"
          @click="submit(false)"
          >{{ $t('mcpAuthorize.deny') }}</Button
        >
        <Button
          type="primary"
          :loading="loading"
          :disabled="loading || !canAllow"
          data-test="mcp-authorize-allow"
          @click="submit(true)"
          >{{ $t('mcpAuthorize.allow') }}</Button
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import MCPOAuthService from '@baserow/modules/core/services/mcpOAuth'
import { notifyIf } from '@baserow/modules/core/utils/error'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const route = useRoute()
const { $client } = useNuxtApp()
const { t } = useI18n()

/**
 * Decodes the unpadded base64url `request` param the backend puts the original
 * authorize query string in. base64url survives the login redirect's
 * `encodeURI` and the router untouched, unlike a plain query string.
 */
function decodeRequest(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) {
    return ''
  }
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  try {
    const bytes = Uint8Array.from(atob(padded), (c) => c.charCodeAt(0))
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return ''
  }
}

// The raw query string of the original authorize request.
const query = decodeRequest(route.query.request)

const workspaceId = ref(null)
// Tool name -> whether the user leaves it ticked.
const ticked = reactive({})
const loading = ref(false)
const error = ref({ visible: false, title: '', message: '' })

const { data: consent } = await useAsyncData('mcp-consent', async () => {
  try {
    const { data } = await MCPOAuthService($client).getConsent(query)
    return data
  } catch (e) {
    error.value = {
      visible: true,
      title: t('mcpAuthorize.invalid'),
      message: e.handler?.response?.data?.error || '',
    }
    return null
  }
})
workspaceId.value = consent.value?.workspaces[0]?.id ?? null
for (const tool of consent.value?.tools || []) {
  ticked[tool.name] = true
}

const toolGroups = computed(() => {
  const tools = consent.value?.tools || []
  return [
    {
      key: 'read',
      label: 'mcpAuthorize.toolsRead',
      tools: tools.filter((tool) => tool.read_only),
    },
    {
      key: 'change',
      label: 'mcpAuthorize.toolsChange',
      tools: tools.filter((tool) => !tool.read_only),
    },
  ].filter((group) => group.tools.length)
})

// Ticked tool names, in the order the API listed them.
const selectedTools = computed(() =>
  (consent.value?.tools || [])
    .map((tool) => tool.name)
    .filter((name) => ticked[name])
)

const canAllow = computed(
  () => workspaceId.value !== null && selectedTools.value.length > 0
)

async function submit(allow) {
  loading.value = true
  error.value = { visible: false, title: '', message: '' }
  const values = { query, allow }
  if (allow) {
    values.workspace_id = workspaceId.value
    values.tools = selectedTools.value
  }
  try {
    const { data } = await MCPOAuthService($client).submitConsent(values)
    window.location.assign(data.redirect_url)
  } catch (e) {
    loading.value = false
    error.value = {
      visible: true,
      title: t('mcpAuthorize.failed'),
      message: '',
    }
    notifyIf(e)
  }
}
</script>
