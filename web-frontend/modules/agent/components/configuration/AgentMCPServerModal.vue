<template>
  <Modal ref="modal" small @hidden="confirmingRemove = false">
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
          :label="$t('agent.connectedAppHeaderName')"
          :helper-text="$t('agent.connectedAppHeaderNameHelper')"
          small-label
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
            {{ server ? $t('action.save') : $t('agent.connectedAppConnect') }}
          </Button>
        </div>
      </form>
    </template>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Adds or edits an MCP server. The credential is write-only: an empty field
 * keeps the stored one, unless the URL or header changes, which the backend
 * only allows with the credential supplied again.
 */
const props = defineProps({
  save: { type: Function, required: true },
  remove: { type: Function, required: true },
})
const emit = defineEmits(['created'])
const { t } = useI18n()

const modal = ref(null)
const server = ref(null)
const touched = ref(false)
const saving = ref(false)
const removing = ref(false)
const confirmingRemove = ref(false)
const error = ref(null)
const values = reactive({
  name: '',
  url: '',
  auth_header_name: '',
  auth_header_value: '',
})

const validUrl = computed(() => {
  try {
    return ['http:', 'https:'].includes(new URL(values.url.trim()).protocol)
  } catch {
    return false
  }
})
const secretRequired = computed(
  () =>
    Boolean(server.value?.has_auth_header_value) &&
    (values.url.trim() !== server.value.url ||
      values.auth_header_name.trim() !== server.value.auth_header_name)
)
const errors = computed(() => {
  if (!touched.value) return {}
  return {
    name: values.name.trim() ? '' : t('error.requiredField'),
    url: validUrl.value ? '' : t('agent.connectedAppUrlInvalid'),
    auth_header_value:
      secretRequired.value && !values.auth_header_value
        ? t('agent.connectedAppHeaderValueRequired')
        : '',
  }
})
const headerValueHelper = computed(() => {
  if (secretRequired.value) return t('agent.connectedAppHeaderValueRequired')
  return server.value?.has_auth_header_value
    ? t('agent.connectedAppHeaderValueKept')
    : t('agent.connectedAppHeaderValueHelper')
})

function show(existing = null) {
  server.value = existing
  Object.assign(values, {
    name: existing?.name ?? '',
    url: existing?.url ?? '',
    auth_header_name: existing?.auth_header_name ?? 'Authorization',
    auth_header_value: '',
  })
  touched.value = false
  error.value = null
  confirmingRemove.value = false
  modal.value.show()
}

function changedValues() {
  const next = {
    name: values.name.trim(),
    url: values.url.trim(),
    auth_header_name: values.auth_header_name.trim(),
  }
  if (values.auth_header_value) {
    next.auth_header_value = values.auth_header_value
  } else if (!server.value) {
    next.auth_header_value = ''
  }
  if (!server.value) return next
  return Object.fromEntries(
    Object.entries(next).filter(
      ([key, value]) =>
        key === 'auth_header_value' || value !== server.value[key]
    )
  )
}

async function submit() {
  touched.value = true
  if (Object.values(errors.value).some(Boolean)) return
  saving.value = true
  error.value = null
  try {
    const isNew = !server.value
    const saved = await props.save(server.value, changedValues())
    modal.value.hide()
    if (isNew) emit('created', saved)
  } catch (e) {
    error.value = e.handler ? e.handler.getMessage() : null
    e.handler?.handled()
    if (!error.value) throw e
  } finally {
    saving.value = false
  }
}

async function confirmRemove() {
  removing.value = true
  error.value = null
  try {
    await props.remove(server.value)
    modal.value.hide()
  } catch (e) {
    error.value = e.handler ? e.handler.getMessage() : null
    e.handler?.handled()
    if (!error.value) throw e
  } finally {
    removing.value = false
  }
}

defineExpose({ show })
</script>
