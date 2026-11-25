<template>
  <article class="agent-action-card agent-mcp-server-card" :aria-busy="busy">
    <header class="agent-action-card__header">
      <button
        type="button"
        class="agent-action-card__toggle"
        :aria-expanded="expanded"
        @click="$emit('toggle')"
      >
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
        <Icon icon="iconoir-server" aria-hidden="true" />
        <span class="agent-action-card__title agent-mcp-server-card__name">{{
          server?.name || $t('agent.connectedAppNew')
        }}</span>
        <Badge
          :color="status.color"
          size="small"
          class="agent-mcp-server-card__status"
          >{{ status.label }}</Badge
        >
      </button>
      <SwitchInput
        v-if="server && editable"
        small
        role="switch"
        tabindex="0"
        :aria-label="$t('agent.connectedAppEnabled', { name: server.name })"
        :aria-checked="server.enabled"
        :model-value="server.enabled"
        @update:model-value="$emit('switch', $event)"
        @keydown.enter.prevent="$emit('switch', !server.enabled)"
        @keydown.space.prevent="$emit('switch', !server.enabled)"
      />
    </header>
    <form
      v-show="expanded"
      class="agent-action-card__body agent-mcp-server-card__body"
      @submit.prevent="submit"
    >
      <FormGroup
        :label="$t('agent.connectedAppName')"
        :error="Boolean(errors.name)"
        :error-message="errors.name"
        small-label
        horizontal
        required
      >
        <FormInput
          v-model="values.name"
          :disabled="!editable"
          :maxlength="255"
          :placeholder="$t('agent.connectedAppNamePlaceholder')"
        />
      </FormGroup>
      <FormGroup
        :label="$t('agent.connectedAppUrl')"
        :error="Boolean(errors.url)"
        :error-message="errors.url"
        small-label
        horizontal
        required
      >
        <FormInput
          v-model="values.url"
          :disabled="!editable"
          :maxlength="2000"
          placeholder="https://example.com/mcp"
        />
      </FormGroup>
      <FormGroup
        class="agent-mcp-server-card__auth-group"
        :label="$t('agent.connectedAppAuth')"
        small-label
        horizontal
        required
      >
        <SegmentControl
          class="agent-connected-apps__auth"
          :segments="authSegments"
          :active-index="authIndex"
          :disabled="!editable"
          size="small"
          @update:active-index="
            editable && (values.auth_type = AUTH_TYPES[$event])
          "
        />
      </FormGroup>

      <template v-if="values.auth_type === MCP_AUTH_TYPE.OAUTH">
        <p class="agent-connected-apps__auth-help">
          {{ $t('agent.connectedAppOAuthHelper') }}
        </p>
        <div
          v-if="server?.auth_type === MCP_AUTH_TYPE.OAUTH"
          class="agent-mcp-server-card__account"
        >
          <template v-if="server.oauth_connected">
            <Icon icon="iconoir-shield-check" type="success" size="small" />
            <span class="agent-mcp-server-card__account-text">{{
              $t('agent.connectedAppSignedIn')
            }}</span>
            <ButtonText
              v-if="editable"
              type="secondary"
              size="small"
              button-type="button"
              :loading="disconnecting"
              @click="disconnectAccount"
            >
              {{ $t('agent.connectedAppDisconnect') }}
            </ButtonText>
          </template>
          <template v-else>
            <Icon icon="iconoir-warning-triangle" type="warning" size="small" />
            <span class="agent-mcp-server-card__account-text">{{
              $t('agent.connectedAppNotConnected')
            }}</span>
            <ButtonText
              v-if="editable && !dirty"
              size="small"
              button-type="submit"
              :loading="saving"
            >
              {{ $t('agent.connectedAppSignIn') }}
            </ButtonText>
          </template>
        </div>
        <template v-if="editable">
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
      </template>

      <template v-else-if="values.auth_type === MCP_AUTH_TYPE.HEADER">
        <FormGroup
          class="margin-top-2"
          :label="$t('agent.connectedAppHeaderName')"
          :error="Boolean(errors.auth_header_name)"
          :error-message="errors.auth_header_name"
          small-label
          horizontal
          required
        >
          <FormInput
            v-model="values.auth_header_name"
            :disabled="!editable"
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
          horizontal
          required
        >
          <FormInput
            v-model="values.auth_header_value"
            :disabled="!editable"
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

      <FormGroup
        v-if="server && !needsAccount"
        class="agent-mcp-server-card__tools"
        :label="$t('agent.connectedAppTools')"
        small-label
        horizontal
      >
        <button
          type="button"
          class="agent-mcp-server-card__tools-button"
          @click="$emit('open-tools', server)"
        >
          <span class="agent-mcp-server-card__tools-summary">{{
            toolsSummary
          }}</span>
          <Icon icon="iconoir-nav-arrow-right" aria-hidden="true" />
        </button>
      </FormGroup>

      <Alert v-if="error" class="margin-top-2" type="error">
        <template #title>{{ error.title }}</template>
        {{ error.message }}
      </Alert>

      <div v-if="editable && dirty" class="agent-mcp-server-card__actions">
        <Button type="secondary" button-type="button" @click="cancel">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="primary" button-type="submit" :loading="saving">
          {{ submitLabel }}
        </Button>
      </div>
    </form>
    <footer v-if="editable" v-show="expanded" class="agent-action-card__footer">
      <ButtonText
        v-if="!confirmingRemove"
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        @click="startRemove"
        >{{ $t('agent.connectedAppRemove') }}</ButtonText
      >
      <ButtonText
        v-else
        type="danger"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        :loading="removing"
        @click="confirmRemove"
        >{{ $t('agent.connectedAppRemoveConfirm') }}</ButtonText
      >
    </footer>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import Icon from '@baserow/modules/core/components/Icon'
import { MCP_AUTH_TYPE } from '@baserow/modules/agent/constants'
import { openSignInPopup } from '@baserow/modules/agent/composables/useAgentMCPServers'
import {
  MCPSignInCancelled,
  MCPSignInError,
  mcpErrorMessage,
} from '@baserow/modules/agent/utils/mcp'

/**
 * One MCP server of an Agent, edited in place: its name, URL and how it
 * authenticates (OAuth sign-in, a static header, or nothing). The on/off
 * switch saves at once; every other field waits for the Save or Sign in
 * button, so a half-typed URL never reaches the server. Credentials are
 * write-only: an empty field keeps the stored one, unless the URL or the
 * header or client it belongs to changes, which the backend only allows with
 * the credential entered again. A null `server` is a draft not saved yet.
 */
const props = defineProps({
  server: { type: Object, default: null },
  expanded: Boolean,
  editable: Boolean,
  save: { type: Function, required: true },
  remove: { type: Function, required: true },
  connect: { type: Function, required: true },
  disconnect: { type: Function, required: true },
  refresh: { type: Function, required: true },
})
const emit = defineEmits(['toggle', 'switch', 'open-tools', 'saved', 'discard'])
const { t } = useI18n()

const AUTH_TYPES = [
  MCP_AUTH_TYPE.OAUTH,
  MCP_AUTH_TYPE.HEADER,
  MCP_AUTH_TYPE.NONE,
]

const touched = ref(false)
const saving = ref(false)
const removing = ref(false)
const disconnecting = ref(false)
const confirmingRemove = ref(false)
const showOwnClient = ref(false)
const error = ref(null)
// Bumped when the edits are dropped or the card goes away, so a request that
// finishes after that is ignored.
let generation = 0
let signIn = null
// A draft's tools start all selected, also when its first sign-in is retried.
const firstConnection = ref(!props.server)
const values = reactive({})

const authSegments = computed(() => [
  { label: t('agent.connectedAppAuthOAuth') },
  { label: t('agent.connectedAppAuthHeader') },
  { label: t('agent.connectedAppAuthNone') },
])
const authIndex = computed(() => AUTH_TYPES.indexOf(values.auth_type))

const needsAccount = computed(
  () =>
    props.server?.auth_type === MCP_AUTH_TYPE.OAUTH &&
    !props.server.oauth_connected
)
const changedCount = computed(
  () =>
    (props.server?.tools ?? []).filter((tool) => tool.changed_since_review)
      .length
)
const status = computed(() => {
  if (!props.server || needsAccount.value)
    return { color: 'yellow', label: t('agent.connectedAppNotConnected') }
  if (changedCount.value)
    return {
      color: 'yellow',
      label: t(
        'agent.connectedAppChanged',
        { count: changedCount.value },
        changedCount.value
      ),
    }
  return { color: 'green', label: t('agent.connectedAppConnected') }
})
const toolsSummary = computed(() => {
  const tools = (props.server?.tools ?? []).filter((tool) => !tool.removed)
  if (!tools.length) return t('agent.connectedAppNoTools')
  return t('agent.toolsOn', {
    count: tools.filter((tool) => tool.enabled).length,
    total: tools.length,
  })
})

const validUrl = computed(() => {
  try {
    return ['http:', 'https:'].includes(new URL(values.url.trim()).protocol)
  } catch {
    return false
  }
})
const urlChanged = computed(
  () => Boolean(props.server) && values.url.trim() !== props.server.url
)
const headerSecretRequired = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.HEADER &&
    Boolean(props.server?.has_auth_header_value) &&
    (urlChanged.value ||
      values.auth_header_name.trim() !== props.server.auth_header_name)
)
const clientChanged = computed(
  () =>
    Boolean(props.server) &&
    values.oauth_client_id.trim() !== ownClientId(props.server)
)
// Only a secret the editor entered is asked for again; one Baserow got by
// registering itself is replaced on the next sign-in.
const clientSecretRequired = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.OAUTH &&
    Boolean(props.server?.has_oauth_client_secret) &&
    Boolean(ownClientId(props.server)) &&
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
  return props.server?.has_auth_header_value ? '' : t('error.requiredField')
}

const headerValueHelper = computed(() => {
  if (headerSecretRequired.value)
    return t('agent.connectedAppHeaderValueRequired')
  return props.server?.has_auth_header_value
    ? t('agent.connectedAppHeaderValueKept')
    : t('agent.connectedAppHeaderValueHelper')
})
const clientSecretHelper = computed(() =>
  props.server?.has_oauth_client_secret
    ? t('agent.connectedAppHeaderValueKept')
    : t('agent.connectedAppClientSecretHelper')
)
// Saving signs in when the server uses OAuth and its account would be missing.
const needsSignIn = computed(
  () =>
    values.auth_type === MCP_AUTH_TYPE.OAUTH &&
    (!props.server ||
      !props.server.oauth_connected ||
      props.server.auth_type !== MCP_AUTH_TYPE.OAUTH ||
      urlChanged.value ||
      values.oauth_client_id.trim() !== ownClientId(props.server))
)
const submitLabel = computed(() => {
  if (needsSignIn.value) return t('agent.connectedAppSignIn')
  return props.server && !firstConnection.value
    ? t('action.save')
    : t('agent.connectedAppConnect')
})
// A draft always has something to save; a saved server once a field changed.
const dirty = computed(
  () => !props.server || Object.keys(changedValues()).length > 0
)
const busy = computed(
  () => saving.value || removing.value || disconnecting.value
)

/** The client id the editor entered; ids Baserow registered aren't shown. */
function ownClientId(existing) {
  return existing?.oauth_client_source === 'manual'
    ? existing.oauth_client_id
    : ''
}

/** Fill the fields with the server as stored. */
function fill() {
  const existing = props.server
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
}
fill()

/** Drop the edits and anything still waiting for them. */
function reset() {
  generation++
  cancelSignIn()
  fill()
  error.value = null
  saving.value = false
  confirmingRemove.value = false
}

// Another editor's change, or this card's own save, shows in the fields
// unless the editor is changing them.
watch(
  () => props.server,
  () => {
    if (!dirty.value && !saving.value) fill()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  generation++
  cancelSignIn()
})

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
  if (!props.server) return next
  const current = {
    ...props.server,
    oauth_client_id: ownClientId(props.server),
  }
  return Object.fromEntries(
    Object.entries(next).filter(
      ([key, value]) =>
        ['auth_header_value', 'oauth_client_secret'].includes(key) ||
        value !== current[key]
    )
  )
}

/** Gives up on a sign-in still waiting. */
function cancelSignIn() {
  signIn?.abort()
  signIn = null
}

function cancel() {
  if (!props.server) emit('discard')
  else reset()
}

async function submit() {
  touched.value = true
  if (Object.values(errors.value).some(Boolean)) return
  // Opened before any request, or the browser blocks the popup.
  const signingIn = needsSignIn.value
  const popup = signingIn ? openSignInPopup() : null
  const isNew = !props.server
  const changes = changedValues()
  const current = ++generation
  const stale = () => current !== generation
  cancelSignIn()
  const controller = new AbortController()
  if (signingIn) signIn = controller
  saving.value = true
  error.value = null
  let saved = null
  try {
    // Signing in to a server that didn't change saves nothing first.
    saved =
      isNew || Object.keys(changes).length
        ? await props.save(props.server, changes)
        : props.server
    if (stale()) return popup?.close()
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
    // Saved: the fields now match the server, so the footer goes away.
    values.auth_header_value = ''
    values.oauth_client_secret = ''
    touched.value = false
    emit('saved', saved, {
      listTools: signingIn || listing,
      firstConnection: firstConnection.value,
    })
    firstConnection.value = false
  } catch (e) {
    popup?.close()
    if (stale()) return
    if (e instanceof MCPSignInCancelled) return
    error.value = mcpErrorMessage(t, e)
  } finally {
    if (signIn === controller) signIn = null
    if (!stale()) saving.value = false
  }
}

async function disconnectAccount() {
  const current = generation
  disconnecting.value = true
  error.value = null
  try {
    await props.disconnect(props.server)
  } catch (e) {
    if (current === generation) error.value = mcpErrorMessage(t, e)
  } finally {
    disconnecting.value = false
  }
}

function startRemove() {
  if (!props.server) emit('discard')
  else confirmingRemove.value = true
}

async function confirmRemove() {
  removing.value = true
  error.value = null
  try {
    await props.remove(props.server)
  } catch (e) {
    error.value = mcpErrorMessage(t, e)
  } finally {
    removing.value = false
  }
}
</script>
