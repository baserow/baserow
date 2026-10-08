<template>
  <div class="auth__wrapper mcp-authorize">
    <div class="auth__logo">
      <Logo />
    </div>
    <Error :error="error" />
    <div v-if="framed" class="mcp-authorize__card">
      <p class="mcp-authorize__empty" data-test="mcp-authorize-framed">
        {{ $t('mcpAuthorize.framed') }}
      </p>
    </div>
    <div v-else-if="!consent && !error.visible" class="mcp-authorize__card">
      <div class="skeleton" data-test="mcp-authorize-loading">
        <div class="mcp-authorize__header">
          <SkeletonBlock width="100%" height="40px" />
          <SkeletonBlock width="60%" height="20px" />
          <SkeletonBlock width="40%" height="14px" />
        </div>
        <div class="mcp-authorize__divider"></div>
        <SkeletonBlock width="100%" height="36px" />
        <SkeletonBlock width="100%" height="160px" />
      </div>
    </div>
    <template v-if="consent">
      <div class="mcp-authorize__card">
        <div class="mcp-authorize__header">
          <div class="mcp-authorize__pair">
            <div
              class="mcp-authorize__avatar mcp-authorize__avatar--client"
              data-test="mcp-authorize-avatar"
            >
              {{ clientInitial }}
            </div>
            <span class="mcp-authorize__dots">• • •</span>
            <div class="mcp-authorize__avatar mcp-authorize__avatar--baserow">
              <img
                src="@baserow/modules/core/static/img/baserow-icon.svg?url"
                alt=""
              />
            </div>
          </div>
          <h1 class="mcp-authorize__title" data-test="mcp-authorize-title">
            {{ $t('mcpAuthorize.title', { client: clientLabel }) }}
          </h1>
          <p class="mcp-authorize__subtitle">
            {{ $t('mcpAuthorize.subtitle') }}
          </p>
          <Badge
            v-if="consent.verified"
            color="green"
            data-test="mcp-authorize-verified"
            >{{
              $t('mcpAuthorize.verified', { host: consent.verified_host })
            }}</Badge
          >
          <Badge v-else color="yellow" data-test="mcp-authorize-unverified">{{
            $t('mcpAuthorize.unverified', { host: consent.redirect_host })
          }}</Badge>
          <p class="mcp-authorize__returns" data-test="mcp-authorize-returns">
            {{ $t('mcpAuthorize.returns', { host: consent.redirect_host }) }}
          </p>
        </div>
        <div class="mcp-authorize__divider"></div>
        <div
          v-if="consent.loopback_only"
          class="mcp-authorize__warning"
          data-test="mcp-authorize-loopback-warning"
        >
          {{ $t('mcpAuthorize.loopbackWarning') }}
        </div>
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
              :description="databasesLabel(workspace.database_count)"
              :data-test="`mcp-authorize-workspace-${workspace.id}`"
            />
          </Dropdown>
        </FormGroup>
        <div class="mcp-authorize__section-head">
          <span class="mcp-authorize__section-label">{{
            $t('mcpAuthorize.tools')
          }}</span>
          <span class="mcp-authorize__links">
            <button
              type="button"
              class="mcp-authorize__link"
              data-test="mcp-authorize-select-all"
              @click="setAll(true)"
            >
              {{ $t('mcpAuthorize.selectAll') }}
            </button>
            <span aria-hidden="true"> · </span>
            <button
              type="button"
              class="mcp-authorize__link"
              data-test="mcp-authorize-select-none"
              @click="setAll(false)"
            >
              {{ $t('mcpAuthorize.selectNone') }}
            </button>
          </span>
        </div>
        <p v-if="!consent.tools.length" class="mcp-authorize__empty">
          {{ $t('mcpAuthorize.noTools') }}
        </p>
        <div v-else class="mcp-authorize__tools">
          <div
            v-for="group in toolGroups"
            :key="group.key"
            :data-test="`mcp-authorize-tools-${group.key}`"
          >
            <div class="mcp-authorize__tool-group-title">
              {{ $t(group.label) }}
            </div>
            <div
              v-for="tool in group.tools"
              :key="tool.name"
              class="mcp-authorize__tool"
            >
              <Checkbox
                v-model="ticked[tool.name]"
                class="mcp-authorize__tool-checkbox"
                :data-test="`mcp-authorize-tool-${tool.name}`"
              >
                {{ tool.title }}
              </Checkbox>
              <Badge
                v-if="tool.destructive"
                :color="isDelete(tool) ? 'red' : 'yellow'"
                size="small"
                class="mcp-authorize__tool-badge"
                :data-test="`mcp-authorize-badge-${tool.name}`"
                >{{
                  isDelete(tool)
                    ? $t('mcpAuthorize.deletes')
                    : $t('mcpAuthorize.overwrites')
                }}</Badge
              >
            </div>
          </div>
        </div>
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
      <p class="mcp-authorize__signed-in" data-test="mcp-authorize-signed-in">
        {{ $t('mcpAuthorize.signedIn', { email: username }) }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MCPOAuthService from '@baserow/modules/core/services/mcpOAuth'
import { notifyIf } from '@baserow/modules/core/utils/error'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const route = useRoute()
const { $client, $store: store } = useNuxtApp()
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
// The frame headers only cover a full load of this page. After logging in inside
// a frame, the router navigates here client side, so check for a frame here too.
const framed = ref(false)

// Client only: the defaults below are applied when the data arrives, so a
// server-rendered form would ship unticked checkboxes that hydration can't fix.
const { data: consent } = useAsyncData(
  `mcp-consent-${route.query.request}`,
  async () => {
    if (window.top !== window.self) {
      framed.value = true
      return null
    }
    try {
      const { data } = await MCPOAuthService($client).getConsent(query)
      applyDefaults(data)
      return data
    } catch (e) {
      error.value = {
        visible: true,
        title: t('mcpAuthorize.invalid'),
        message: e.handler?.response?.data?.error || '',
      }
      return null
    }
  },
  { server: false }
)

// Preselect the first workspace that has databases, so the user doesn't land on
// an empty one, and tick every tool. Runs before the form is first rendered.
function applyDefaults(value) {
  const workspaces = value?.workspaces || []
  const preferred =
    workspaces.find((workspace) => workspace.database_count > 0) ||
    workspaces[0]
  workspaceId.value = preferred?.id ?? null
  tickFor(workspaceId.value, value)
}

// A workspace the client is already connected to starts from that grant's tools,
// so reconnecting never widens access unnoticed. Otherwise every tool is ticked.
function tickFor(id, value = consent.value) {
  const existing = value?.grants?.[id]
  for (const tool of value?.tools || []) {
    ticked[tool.name] = existing ? existing.includes(tool.name) : true
  }
}

watch(workspaceId, (id) => tickFor(id))

const username = computed(() => store.getters['auth/getUsername'])
// A verified client is named by its host; anything else is self-declared.
const clientLabel = computed(() =>
  consent.value?.verified
    ? consent.value.verified_host
    : consent.value?.client_name || ''
)
const clientInitial = computed(() =>
  clientLabel.value.trim().charAt(0).toUpperCase()
)

function databasesLabel(count) {
  return t('mcpAuthorize.databases', { count: count || 0 })
}

function isDelete(tool) {
  return tool.name.startsWith('delete_')
}

function setAll(value) {
  for (const tool of consent.value?.tools || []) {
    ticked[tool.name] = value
  }
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
