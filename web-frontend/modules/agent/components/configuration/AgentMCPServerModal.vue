<template>
  <Modal ref="modal" small @hidden="hidden">
    <template #content>
      <h2 class="box__title">
        {{
          server
            ? $t('agent.connectedAppEditTitle')
            : $t('agent.connectedAppAdd')
        }}
      </h2>
      <form @submit.prevent="submit">
        <FormGroup
          :label="$t('agent.connectedAppName')"
          :error="Boolean(errors.name)"
          :error-message="errors.name"
          small-label
          required
        >
          <FormInput
            v-model="values.name"
            :maxlength="255"
            :placeholder="$t('agent.connectedAppNamePlaceholder')"
          />
        </FormGroup>
        <FormGroup
          class="margin-top-2"
          :label="$t('agent.connectedAppUrl')"
          :helper-text="$t('agent.connectedAppUrlHelper')"
          :error="Boolean(errors.url)"
          :error-message="errors.url"
          small-label
          required
        >
          <FormInput
            v-model="values.url"
            :maxlength="2000"
            placeholder="https://example.com/mcp"
          />
        </FormGroup>
        <FormGroup
          class="margin-top-2"
          :label="$t('agent.connectedAppAuth')"
          small-label
          required
        >
          <SegmentControl
            class="agent-connected-apps__auth"
            :segments="authSegments"
            :active-index="authIndex"
            size="small"
            @update:active-index="values.auth_type = AUTH_TYPES[$event]"
          />
        </FormGroup>

        <template v-if="values.auth_type === MCP_AUTH_TYPE.OAUTH">
          <p class="agent-connected-apps__auth-help">
            {{ $t('agent.connectedAppOAuthHelper') }}
          </p>
          <div v-if="server" class="agent-connected-apps__oauth-status">
            <Badge
              :color="server.oauth_connected ? 'green' : 'yellow'"
              size="small"
              indicator
            >
              {{
                server.oauth_connected
                  ? $t('agent.connectedAppConnected')
                  : $t('agent.connectedAppNotConnected')
              }}
            </Badge>
            <ButtonText
              v-if="server.oauth_connected"
              type="secondary"
              size="small"
              button-type="button"
              :loading="disconnecting"
              @click="disconnectAccount"
            >
              {{ $t('agent.connectedAppDisconnect') }}
            </ButtonText>
          </div>
          <ButtonText
            v-if="!showOwnClient"
            class="margin-top-1"
            size="small"
            button-type="button"
            @click="showOwnClient = true"
          >
            {{ $t('agent.connectedAppOwnClient') }}
          </ButtonText>
          <template v-else>
            <FormGroup
              class="margin-top-2"
              :label="$t('agent.connectedAppClientId')"
              :helper-text="$t('agent.connectedAppClientIdHelper')"
              small-label
            >
              <FormInput v-model="values.oauth_client_id" :maxlength="2000" />
            </FormGroup>
            <FormGroup
              class="margin-top-2"
              :label="$t('agent.connectedAppClientSecret')"
              :helper-text="clientSecretHelper"
              :error="Boolean(errors.oauth_client_secret)"
              :error-message="errors.oauth_client_secret"
              small-label
            >
              <FormInput
                v-model="values.oauth_client_secret"
                type="password"
                autocomplete="off"
                :placeholder="server?.has_oauth_client_secret ? '••••••••' : ''"
              />
            </FormGroup>
          </template>
        </template>

        <template v-else-if="values.auth_type === MCP_AUTH_TYPE.HEADER">
          <FormGroup
            class="margin-top-2"
            :label="$t('agent.connectedAppHeaderName')"
            :error="Boolean(errors.auth_header_name)"
            :error-message="errors.auth_header_name"
            small-label
            required
          >
            <FormInput
              v-model="values.auth_header_name"
              :maxlength="255"
              placeholder="Authorization"
            />
          </FormGroup>
          <FormGroup
            class="margin-top-2"
            :label="$t('agent.connectedAppHeaderValue')"
            :helper-text="headerValueHelper"
            :error="Boolean(errors.auth_header_value)"
            :error-message="errors.auth_header_value"
            small-label
            required
          >
            <FormInput
              v-model="values.auth_header_value"
              type="password"
              autocomplete="off"
              :placeholder="
                server?.has_auth_header_value ? '••••••••' : 'Bearer …'
              "
            />
          </FormGroup>
        </template>

        <p v-else class="agent-connected-apps__auth-help">
          {{ $t('agent.connectedAppNoAuthHelper') }}
        </p>

        <Alert v-if="error" class="margin-top-2" type="error">
          <template #title>{{ error.title }}</template>
          {{ error.message }}
        </Alert>
        <div class="agent-connected-apps__modal-actions">
          <template v-if="server">
            <Button
              v-if="!confirmingRemove"
              type="secondary"
              button-type="button"
              icon="iconoir-trash"
              @click="confirmingRemove = true"
            >
              {{ $t('agent.connectedAppRemove') }}
            </Button>
            <Button
              v-else
              type="danger"
              button-type="button"
              :loading="removing"
              @click="confirmRemove"
            >
              {{ $t('agent.connectedAppRemoveConfirm') }}
            </Button>
          </template>
          <span class="agent-connected-apps__modal-spacer"></span>
          <Button type="secondary" button-type="button" @click="modal.hide()">
            {{ $t('action.cancel') }}
          </Button>
          <Button type="primary" button-type="submit" :loading="saving">
            {{ submitLabel }}
          </Button>
        </div>
      </form>
    </template>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import { MCP_AUTH_TYPE } from '@baserow/modules/agent/constants'
import { openSignInPopup } from '@baserow/modules/agent/composables/useAgentMCPServers'
import {
  MCPSignInCancelled,
  MCPSignInError,
  mcpErrorMessage,
} from '@baserow/modules/agent/utils/mcp'

/**
 * Adds or edits an MCP server and how it authenticates: OAuth sign-in, a
 * static header, or nothing. Credentials are write-only: an empty field keeps
 * the stored one, unless the URL or the header or client it belongs to
 * changes, which the backend only allows with the credential entered again.
 * The fields below that check this only say so before saving.
 */
const props = defineProps({
  save: { type: Function, required: true },
  remove: { type: Function, required: true },
  connect: { type: Function, required: true },
  disconnect: { type: Function, required: true },
  refresh: { type: Function, required: true },
})
const emit = defineEmits(['created'])
const { t } = useI18n()

const AUTH_TYPES = [
  MCP_AUTH_TYPE.OAUTH,
  MCP_AUTH_TYPE.HEADER,
  MCP_AUTH_TYPE.NONE,
]

const modal = ref(null)
const server = ref(null)
const touched = ref(false)
const saving = ref(false)
const removing = ref(false)
const disconnecting = ref(false)
const confirmingRemove = ref(false)
const showOwnClient = ref(false)
const error = ref(null)
// Bumped each time the modal opens, so a request that finishes after the
// editor moved on to another server or opening is ignored.
let opening = 0
let signIn = null
const values = reactive({
  name: '',
  url: '',
  auth_type: MCP_AUTH_TYPE.OAUTH,
  auth_header_name: '',
  auth_header_value: '',
  oauth_client_id: '',
  oauth_client_secret: '',
})

const authSegments = computed(() => [
  { label: t('agent.connectedAppAuthOAuth') },
  { label: t('agent.connectedAppAuthHeader') },
  { label: t('agent.connectedAppAuthNone') },
])
const authIndex = computed(() => AUTH_TYPES.indexOf(values.auth_type))

const validUrl = computed(() => {
  try {
    return ['http:', 'https:'].includes(new URL(values.url.trim()).protocol)
  } catch {
    return false
  }
})
const urlChanged = computed(
  () => Boolean(server.value) && values.url.trim() !== server.value.url
)
const headerSecretRequired = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.HEADER &&
    Boolean(server.value?.has_auth_header_value) &&
    (urlChanged.value ||
      values.auth_header_name.trim() !== server.value.auth_header_name)
)
const clientChanged = computed(
  () =>
    Boolean(server.value) &&
    values.oauth_client_id.trim() !== ownClientId(server.value)
)
// Only a secret the editor entered is asked for again; one Baserow got by
// registering itself is replaced on the next sign-in.
const clientSecretRequired = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.OAUTH &&
    Boolean(server.value?.has_oauth_client_secret) &&
    Boolean(ownClientId(server.value)) &&
    // Clearing the client id goes back to Baserow registering itself.
    Boolean(values.oauth_client_id.trim()) &&
    (urlChanged.value || clientChanged.value)
)
const errors = computed(() => {
  if (!touched.value) return {}
  return {
    name: values.name.trim() ? '' : t('error.requiredField'),
    url: validUrl.value ? '' : t('agent.connectedAppUrlInvalid'),
    auth_header_name:
      values.auth_type === MCP_AUTH_TYPE.HEADER &&
      !values.auth_header_name.trim()
        ? t('error.requiredField')
        : '',
    auth_header_value: headerValueError(),
    oauth_client_secret:
      clientSecretRequired.value && !values.oauth_client_secret
        ? t('agent.connectedAppClientSecretRequired')
        : '',
  }
})
function headerValueError() {
  if (values.auth_type !== MCP_AUTH_TYPE.HEADER || values.auth_header_value) {
    return ''
  }
  if (headerSecretRequired.value) {
    return t('agent.connectedAppHeaderValueRequired')
  }
  // A new key is needed unless one is stored already.
  return server.value?.has_auth_header_value ? '' : t('error.requiredField')
}

const headerValueHelper = computed(() => {
  if (headerSecretRequired.value)
    return t('agent.connectedAppHeaderValueRequired')
  return server.value?.has_auth_header_value
    ? t('agent.connectedAppHeaderValueKept')
    : t('agent.connectedAppHeaderValueHelper')
})
const clientSecretHelper = computed(() =>
  server.value?.has_oauth_client_secret
    ? t('agent.connectedAppHeaderValueKept')
    : t('agent.connectedAppClientSecretHelper')
)
// Saving signs in when the server uses OAuth and its account would be missing.
const needsSignIn = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.OAUTH &&
    (!server.value ||
      !server.value.oauth_connected ||
      server.value.auth_type !== MCP_AUTH_TYPE.OAUTH ||
      urlChanged.value ||
      values.oauth_client_id.trim() !== ownClientId(server.value))
)
const submitLabel = computed(() => {
  if (needsSignIn.value) return t('agent.connectedAppSignIn')
  return server.value ? t('action.save') : t('agent.connectedAppConnect')
})

/** The client id the editor entered; ids Baserow registered aren't shown. */
function ownClientId(existing) {
  return existing?.oauth_client_source === 'manual'
    ? existing.oauth_client_id
    : ''
}

function show(existing = null) {
  opening++
  cancelSignIn()
  saving.value = false
  removing.value = false
  disconnecting.value = false
  server.value = existing
  Object.assign(values, {
    name: existing?.name ?? '',
    url: existing?.url ?? '',
    auth_type: existing?.auth_type ?? MCP_AUTH_TYPE.OAUTH,
    auth_header_name: existing?.auth_header_name || 'Authorization',
    auth_header_value: '',
    oauth_client_id: ownClientId(existing),
    oauth_client_secret: '',
  })
  showOwnClient.value = Boolean(values.oauth_client_id)
  touched.value = false
  error.value = null
  confirmingRemove.value = false
  modal.value.show()
}

/**
 * The values the editor changed. A credential is only sent when entered: the
 * backend keeps a stored one, or clears it when the change no longer uses it.
 */
function changedValues() {
  const next = {
    name: values.name.trim(),
    url: values.url.trim(),
    auth_type: values.auth_type,
  }
  if (values.auth_type === MCP_AUTH_TYPE.HEADER) {
    next.auth_header_name = values.auth_header_name.trim()
    if (values.auth_header_value) {
      next.auth_header_value = values.auth_header_value
    }
  } else if (values.auth_type === MCP_AUTH_TYPE.OAUTH) {
    next.oauth_client_id = values.oauth_client_id.trim()
    if (values.oauth_client_secret) {
      next.oauth_client_secret = values.oauth_client_secret
    }
  }
  if (!server.value) return next
  const current = {
    ...server.value,
    oauth_client_id: ownClientId(server.value),
  }
  return Object.fromEntries(
    Object.entries(next).filter(
      ([key, value]) =>
        ['auth_header_value', 'oauth_client_secret'].includes(key) ||
        value !== current[key]
    )
  )
}

/** Gives up on a sign-in still waiting, e.g. when the modal closes. */
function cancelSignIn() {
  signIn?.abort()
  signIn = null
}

function hidden() {
  confirmingRemove.value = false
  cancelSignIn()
}

async function submit() {
  touched.value = true
  if (Object.values(errors.value).some(Boolean)) return
  // Opened before any request, or the browser blocks the popup.
  const signingIn = needsSignIn.value
  const popup = signingIn ? openSignInPopup() : null
  const isNew = !server.value
  const current = opening
  const stale = () => current !== opening
  cancelSignIn()
  const controller = new AbortController()
  if (signingIn) signIn = controller
  saving.value = true
  error.value = null
  try {
    let saved = await props.save(server.value, changedValues())
    if (stale()) return popup?.close()
    // A failed sign-in keeps the modal open on the server that now exists.
    server.value = saved
    if (signingIn && !popup) {
      throw new MCPSignInError(t('agent.connectedAppPopupBlocked'))
    } else if (signingIn) {
      saved = await props.connect(saved, popup, controller.signal)
    }
    if (stale()) return
    // A server without tools, being new, moved, or after a refused key, lists
    // them on save, so they can be reviewed and a wrong key shows here.
    const listing = !signingIn && (isNew || !saved.tools.length)
    if (listing) saved = await props.refresh(saved)
    if (stale()) return
    modal.value.hide()
    if (signingIn || listing) emit('created', saved)
  } catch (e) {
    popup?.close()
    if (e instanceof MCPSignInCancelled) return
    const message = mcpErrorMessage(t, e)
    if (!stale()) error.value = message
  } finally {
    if (signIn === controller) signIn = null
    if (!stale()) saving.value = false
  }
}

async function disconnectAccount() {
  const current = opening
  disconnecting.value = true
  error.value = null
  try {
    const disconnected = await props.disconnect(server.value)
    if (current === opening) server.value = disconnected
  } catch (e) {
    const message = mcpErrorMessage(t, e)
    if (current === opening) error.value = message
  } finally {
    if (current === opening) disconnecting.value = false
  }
}

async function confirmRemove() {
  const current = opening
  removing.value = true
  error.value = null
  try {
    await props.remove(server.value)
    if (current === opening) modal.value.hide()
  } catch (e) {
    const message = mcpErrorMessage(t, e)
    if (current === opening) error.value = message
  } finally {
    if (current === opening) removing.value = false
  }
}

defineExpose({ show })
</script>
