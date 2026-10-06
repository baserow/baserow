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
      <FormGroup :label="$t('mcpAuthorize.endpoint')" required>
        <Dropdown v-model="selected" :show-search="false">
          <DropdownItem
            v-for="endpoint in consent.endpoints"
            :key="endpoint.id"
            :name="`${endpoint.name} (${endpoint.workspace_name})`"
            :value="endpoint.id"
          />
          <DropdownItem :name="$t('mcpAuthorize.createNew')" :value="NEW" />
        </Dropdown>
      </FormGroup>
      <template v-if="selected === NEW">
        <FormGroup :label="$t('mcpAuthorize.newName')" required>
          <FormInput v-model="newName" />
        </FormGroup>
        <FormGroup :label="$t('mcpAuthorize.newWorkspace')" required>
          <Dropdown v-model="newWorkspaceId" :show-search="false">
            <DropdownItem
              v-for="workspace in workspaces"
              :key="workspace.id"
              :name="workspace.name"
              :value="workspace.id"
            />
          </Dropdown>
        </FormGroup>
      </template>
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
import { computed, ref } from 'vue'
import MCPOAuthService from '@baserow/modules/core/services/mcpOAuth'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const NEW = 'new'
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

const selected = ref(null)
const newName = ref('')
const newWorkspaceId = ref(null)
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
selected.value = consent.value?.endpoints.length
  ? consent.value.endpoints[0].id
  : NEW

const { data: workspaces } = await useAsyncData(
  'mcp-consent-workspaces',
  async () => {
    const { data } = await WorkspaceService($client).fetchAll()
    return data
  }
)

const canAllow = computed(() =>
  selected.value === NEW
    ? newName.value.trim() !== '' && newWorkspaceId.value !== null
    : selected.value !== null
)

async function submit(allow) {
  loading.value = true
  error.value = { visible: false, title: '', message: '' }
  const values = { query, allow }
  if (allow && selected.value === NEW) {
    values.new_endpoint = {
      name: newName.value.trim(),
      workspace_id: newWorkspaceId.value,
    }
  } else if (allow) {
    values.endpoint_id = selected.value
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
