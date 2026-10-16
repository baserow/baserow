import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useNuxtApp } from '#app'
import debounce from 'lodash/debounce'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'

const CONFIGURATION_FIELDS = [
  'name',
  'instructions',
  'provider_type',
  'model_identifier',
]

const emptyConfiguration = () => ({
  name: '',
  instructions: '',
  provider_type: null,
  model_identifier: null,
})

/** Page-local Agent settings, kept out of the shared application store. */
export function useAgentConfiguration(agent) {
  const store = useStore()
  const { $client, $hasPermission } = useNuxtApp()
  const service = AgentApplicationService($client)
  const permission = (operation) =>
    Boolean(
      agent.value &&
      $hasPermission(operation, agent.value, agent.value.workspace.id)
    )

  const canReadSettings = computed(() =>
    permission('agent_application.read_settings')
  )
  const canUpdateSettings = computed(() => permission('application.update'))

  const readiness = ref(null)
  const readinessLoading = ref(false)
  const readinessError = ref(false)
  const availabilityLoading = ref(false)
  const availabilityError = ref(false)
  const configuration = reactive(emptyConfiguration())
  const savedConfiguration = ref(null)
  const configurationErrors = ref({})
  const configurationLoading = ref(false)
  const configurationLoadError = ref(false)
  const pendingSettings = reactive({})
  const savingSettings = ref(false)
  const settingsSaveError = ref(false)

  let scope = 0
  let readinessRequest = 0
  let availabilityRequest = 0
  let configurationRequest = 0
  let applyingName = false
  let refreshPending = false
  let inFlightSettings = {}
  let settingsSavePromise = null

  const workspace = computed(() =>
    agent.value
      ? store.getters['workspace/get'](agent.value.workspace.id)
      : null
  )
  const enabledModels = computed(() =>
    getEnabledModelsForAIProviderFeature(workspace.value, 'ai_agent')
  )
  const hasPendingSettings = computed(
    () => Object.keys(pendingSettings).length > 0
  )
  const fieldErrors = computed(() => {
    const saved = savedConfiguration.value
    if (!canReadSettings.value || !saved) return {}

    const errors = {}
    for (const field of CONFIGURATION_FIELDS) {
      if (!(configuration[field] || '').trim()) {
        errors[field] = 'required'
      } else if (
        configurationErrors.value[field] === 'unavailable' &&
        configuration[field] === saved[field] &&
        (field !== 'model_identifier' ||
          configuration.provider_type === saved.provider_type)
      ) {
        // The backend's error outranks an older cached model list.
        errors[field] = 'unavailable'
      }
    }
    if (!availabilityLoading.value && !availabilityError.value) {
      const provider = configuration.provider_type
      const models = enabledModels.value[provider] || []
      if (provider && !models.length) errors.provider_type = 'unavailable'
      if (
        provider &&
        configuration.model_identifier &&
        !models.includes(configuration.model_identifier)
      ) {
        errors.model_identifier = 'unavailable'
      }
    }
    return errors
  })
  const scopeIsCurrent = (currentScope) => scope === currentScope

  async function fetchReadiness() {
    if (!agent.value) return
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++readinessRequest
    readinessLoading.value = true
    readinessError.value = false
    try {
      const { data } = await service.getReadiness(agentId)
      if (!scopeIsCurrent(currentScope) || request !== readinessRequest) return
      readiness.value = data.state
    } catch {
      if (!scopeIsCurrent(currentScope) || request !== readinessRequest) return
      readiness.value = null
      readinessError.value = true
    } finally {
      if (scopeIsCurrent(currentScope) && request === readinessRequest) {
        readinessLoading.value = false
      }
    }
  }

  async function fetchAvailability() {
    if (!agent.value) return
    const currentScope = scope
    const workspaceId = agent.value.workspace.id
    const request = ++availabilityRequest
    availabilityLoading.value = true
    availabilityError.value = false
    try {
      await store.dispatch('workspace/refreshGenerativeAIModels', workspaceId)
    } catch {
      if (scopeIsCurrent(currentScope) && request === availabilityRequest) {
        availabilityError.value = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && request === availabilityRequest) {
        availabilityLoading.value = false
      }
    }
  }

  function applyConfiguration(data, preserveDraft = false) {
    const saved = Object.fromEntries(
      CONFIGURATION_FIELDS.map((field) => [field, data[field]])
    )
    savedConfiguration.value = saved
    for (const field of CONFIGURATION_FIELDS) {
      if (!preserveDraft || !(field in pendingSettings)) {
        configuration[field] = saved[field]
      }
      if (configuration[field] === saved[field]) delete pendingSettings[field]
    }
    configurationErrors.value = data.errors || {}
    ++readinessRequest
    readinessLoading.value = false
    readiness.value = data.state
    readinessError.value = false
  }

  async function fetchConfiguration() {
    if (!canReadSettings.value) return
    if (hasPendingSettings.value || savingSettings.value) {
      refreshPending = true
      return
    }
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++configurationRequest
    configurationLoading.value = true
    configurationLoadError.value = false
    try {
      const { data } = await service.getConfiguration(agentId)
      if (
        !scopeIsCurrent(currentScope) ||
        request !== configurationRequest ||
        !canReadSettings.value
      ) {
        return
      }
      applyConfiguration(data, true)
    } catch {
      if (scopeIsCurrent(currentScope) && request === configurationRequest) {
        configurationLoadError.value = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && request === configurationRequest) {
        configurationLoading.value = false
      }
    }
  }

  const scheduleSave = debounce(() => saveSettings(), 400)

  function updateConfiguration(values) {
    if (!canReadSettings.value || !canUpdateSettings.value) return
    for (const [field, value] of Object.entries(values)) {
      if (!CONFIGURATION_FIELDS.includes(field)) continue
      const normalized =
        ['provider_type', 'model_identifier'].includes(field) && !value
          ? null
          : value
      configuration[field] = normalized
      if (
        savedConfiguration.value?.[field] === normalized &&
        !(field in inFlightSettings)
      ) {
        delete pendingSettings[field]
      } else {
        pendingSettings[field] = normalized
      }
    }
    settingsSaveError.value = false
    scheduleSave()
  }

  function saveSettings() {
    if (savingSettings.value) return settingsSavePromise
    if (
      !canReadSettings.value ||
      !canUpdateSettings.value ||
      !hasPendingSettings.value
    ) {
      return false
    }
    const currentScope = scope
    const application = agent.value
    const agentId = application.id
    const values = { ...pendingSettings }
    // An empty name is a local error; other fields still save incrementally.
    if ('name' in values && !values.name.trim()) delete values.name
    if (!Object.keys(values).length) return false
    savingSettings.value = true
    inFlightSettings = values
    settingsSaveError.value = false
    ++configurationRequest
    settingsSavePromise = (async () => {
      try {
        const { data } = await service.updateConfiguration(agentId, values)
        if (!scopeIsCurrent(currentScope) || !canReadSettings.value) return
        for (const field of Object.keys(values)) {
          if (configuration[field] === values[field])
            delete pendingSettings[field]
        }
        applyConfiguration(data, true)
        // Only public navigation metadata enters the generic application store.
        applyingName = true
        await store.dispatch('application/forceUpdate', {
          application,
          data: { name: data.name },
        })
        applyingName = false
        return true
      } catch {
        if (scopeIsCurrent(currentScope) && canReadSettings.value) {
          settingsSaveError.value = true
        }
        return false
      } finally {
        if (scopeIsCurrent(currentScope)) {
          if (!canReadSettings.value) {
            readiness.value = null
            fetchReadiness()
          }
          savingSettings.value = false
          inFlightSettings = {}
          applyingName = false
          if (hasPendingSettings.value && !settingsSaveError.value) {
            scheduleSave()
          } else if (refreshPending && !settingsSaveError.value) {
            refreshPending = false
            refreshConfiguration()
          }
        }
      }
    })()
    return settingsSavePromise
  }

  async function flushSettings() {
    scheduleSave.cancel()
    const currentScope = scope
    while (scopeIsCurrent(currentScope) && hasPendingSettings.value) {
      const saved = await saveSettings()
      scheduleSave.cancel()
      if (!saved || settingsSaveError.value) break
    }
    return !scopeIsCurrent(currentScope) || !hasPendingSettings.value
  }

  onBeforeRouteLeave(flushSettings)
  onBeforeRouteUpdate(flushSettings)

  async function refreshConfiguration() {
    await Promise.all([
      fetchReadiness(),
      fetchAvailability(),
      fetchConfiguration(),
    ])
  }

  const unsubscribe = store.subscribe((mutation) => {
    if (
      mutation.type === 'application/UPDATE_ITEM' &&
      mutation.payload.id === agent.value?.id &&
      !applyingName
    ) {
      refreshConfiguration()
    }
  })

  function clearSettings() {
    ++configurationRequest
    scheduleSave.cancel()
    Object.assign(configuration, emptyConfiguration())
    savedConfiguration.value = null
    configurationErrors.value = {}
    configurationLoading.value = false
    Object.keys(pendingSettings).forEach(
      (field) => delete pendingSettings[field]
    )
    settingsSaveError.value = false
    readiness.value = null
  }

  function reset() {
    ++scope
    clearSettings()
    readinessLoading.value = false
    readinessError.value = false
    availabilityLoading.value = false
    availabilityError.value = false
    configurationLoadError.value = false
    savingSettings.value = false
    inFlightSettings = {}
    settingsSavePromise = null
    refreshPending = false
  }

  watch(
    () => [agent.value?.id, store.state.auth.user?.id],
    () => {
      reset()
      if (agent.value) refreshConfiguration()
    },
    { immediate: true }
  )
  watch(
    () => JSON.stringify(enabledModels.value),
    () => {
      fetchReadiness()
      fetchConfiguration()
    }
  )
  watch(canReadSettings, (allowed) => {
    if (allowed) {
      fetchConfiguration()
    } else {
      clearSettings()
      fetchReadiness()
    }
  })
  onBeforeUnmount(() => {
    unsubscribe()
    reset()
  })

  return {
    canReadSettings,
    canUpdateSettings,
    readiness,
    readinessLoading,
    readinessError,
    availabilityLoading,
    availabilityError,
    enabledModels,
    configuration,
    fieldErrors,
    configurationLoading,
    configurationLoadError,
    hasPendingSettings,
    savingSettings,
    settingsSaveError,
    updateConfiguration,
    saveSettings,
    refreshConfiguration,
  }
}
