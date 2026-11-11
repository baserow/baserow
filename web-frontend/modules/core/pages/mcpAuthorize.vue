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
          <!-- Any host can publish a metadata document under any name, so a
            verified client's host stays in the title next to its name. -->
          <h1 class="mcp-authorize__title" data-test="mcp-authorize-title">
            {{
              consent.verified
                ? $t('mcpAuthorize.titleFrom', {
                    client: clientLabel,
                    host: consent.verified_host,
                  })
                : $t('mcpAuthorize.title', { client: clientLabel })
            }}
          </h1>
          <p class="mcp-authorize__subtitle">
            {{ $t('mcpAuthorize.subtitle') }}
          </p>
          <Badge
            v-if="!consent.verified"
            color="yellow"
            data-test="mcp-authorize-unverified"
            >{{
              $t('mcpAuthorize.unverified', { host: consent.redirect_host })
            }}</Badge
          >
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
        <McpToolPicker
          v-model="selectedTools"
          :tools="consent.tools"
          :groups="consent.groups || []"
        />
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
import { computed, ref, watch } from 'vue'
import McpToolPicker from '@baserow/modules/core/components/mcp/McpToolPicker'
import MCPOAuthService from '@baserow/modules/core/services/mcpOAuth'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { authenticatedUnlessError } from '@baserow/modules/core/utils/mcpAuthorize'
import {
  grantedToolNames,
  readOnlyToolNames,
} from '@baserow/modules/core/utils/mcpTools'

definePageMeta({
  layout: 'login',
  middleware: ['settings', authenticatedUnlessError],
})

const route = useRoute()
const { $client, $store: store } = useNuxtApp()
const { t } = useI18n()

// The consent page grants a client access, so it must not be framed
// (clickjacking). Set here rather than in a route rule, which would miss other
// spellings of the path that the router also serves.
if (import.meta.server) {
  useResponseHeader('Content-Security-Policy').value = "frame-ancestors 'none'"
  useResponseHeader('X-Frame-Options').value = 'DENY'
}

/**
 * Decodes the unpadded base64url `request` the backend puts the original
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

// The request is in the path, which SSO sign-in keeps. Older backends sent it
// as a query parameter.
const encodedRequest = route.params.request || route.query.request
// The raw query string of the original authorize request.
const query = decodeRequest(encodedRequest)

const workspaceId = ref(null)
// The tool names the user leaves ticked.
const selectedTools = ref([])
const loading = ref(false)
const error = ref({ visible: false, title: '', message: '' })
// The backend sends authorize errors here instead of to the client's redirect
// URI, which can't be trusted before the user has signed in and allowed it.
// Only the code is read, so the URL can't put its own text on the page.
const ERROR_MESSAGES = {
  unknown_client: 'mcpAuthorize.unknownClient',
  client_rejected: 'mcpAuthorize.clientRejected',
}
const routeError = route.query.error
if (routeError) {
  error.value = {
    visible: true,
    title: t('mcpAuthorize.invalid'),
    message: t(
      Object.hasOwn(ERROR_MESSAGES, routeError)
        ? ERROR_MESSAGES[routeError]
        : 'mcpAuthorize.invalidMessage'
    ),
  }
}
// The frame headers only cover a full load of this page. After logging in inside
// a frame, the router navigates here client side, so check for a frame here too.
const framed = ref(false)

// Client only: the defaults below are applied when the data arrives, so a
// server-rendered form would ship unticked checkboxes that hydration can't fix.
const { data: consent } = useAsyncData(
  `mcp-consent-${encodedRequest}`,
  async () => {
    if (error.value.visible) {
      return null
    }
    if (window.top !== window.self) {
      framed.value = true
      return null
    }
    try {
      const { data } = await MCPOAuthService($client).getConsent(query)
      applyDefaults(data)
      return data
    } catch (e) {
      const response = e.handler?.response
      // An outage isn't a broken request, and reloading the page tries again.
      error.value =
        !response || response.status >= 500
          ? {
              visible: true,
              title: t('mcpAuthorize.loadFailed'),
              message: t('mcpAuthorize.loadFailedMessage'),
            }
          : {
              visible: true,
              title: t('mcpAuthorize.invalid'),
              message: response.data?.detail || response.data?.error || '',
            }
      return null
    }
  },
  { server: false }
)

// Preselect the workspace the client is already connected to, so reconnecting
// keeps it there. Otherwise the first workspace that has databases, so the user
// doesn't land on an empty one. Runs before the form is first rendered.
function applyDefaults(value) {
  const workspaces = value?.workspaces || []
  const grants = value?.grants || {}
  const preferred =
    workspaces.find((workspace) => Object.hasOwn(grants, workspace.id)) ||
    workspaces.find((workspace) => workspace.database_count > 0) ||
    workspaces[0]
  workspaceId.value = preferred?.id ?? null
  tickFor(workspaceId.value, value)
}

// A workspace the client is already connected to starts from that grant's tools,
// so reconnecting never widens access unnoticed. Otherwise the "Read only"
// preset, so changing data is opt-in.
function tickFor(id, value = consent.value) {
  // The watcher below can run before the data is stored.
  if (!value) {
    return
  }
  const existing = value.grants?.[id]
  selectedTools.value = existing
    ? grantedToolNames(value.tools, existing)
    : readOnlyToolNames(value.tools, value.groups || [])
}

watch(workspaceId, (id) => tickFor(id))

const username = computed(() => store.getters['auth/getUsername'])
// Named like in Settings.
const clientLabel = computed(() => consent.value?.client_name || '')
const clientInitial = computed(() =>
  clientLabel.value.trim().charAt(0).toUpperCase()
)

function databasesLabel(count) {
  return t('mcpAuthorize.databases', { count: count || 0 })
}

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
