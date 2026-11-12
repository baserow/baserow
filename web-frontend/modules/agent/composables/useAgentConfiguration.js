import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useNuxtApp } from '#app'
import debounce from 'lodash/debounce'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ApplicationService from '@baserow/modules/core/services/application'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { selectAgentApplication } from '@baserow/modules/agent/middleware/selectAgentApplication'
import {
  AGENT_READINESS,
  CONFIGURATION_ERROR,
  CONFIGURATION_FIELD,
  CONFIGURATION_SAVE_RESULT,
  API_ERROR_CODE,
} from '@baserow/modules/agent/constants'

const REQUIRED_FIELDS = [
  CONFIGURATION_FIELD.INSTRUCTIONS,
  CONFIGURATION_FIELD.PROVIDER_TYPE,
  CONFIGURATION_FIELD.MODEL_IDENTIFIER,
]
// What replies send depends on these, so it is unknown until they are saved.
const APPLIED_REASONING_EFFORT_INPUTS = [
  CONFIGURATION_FIELD.PROVIDER_TYPE,
  CONFIGURATION_FIELD.MODEL_IDENTIFIER,
  CONFIGURATION_FIELD.REASONING_EFFORT,
]
const MODEL_FIELDS = [
  CONFIGURATION_FIELD.PROVIDER_TYPE,
  CONFIGURATION_FIELD.MODEL_IDENTIFIER,
]
const TOOL_FIELDS = [
  CONFIGURATION_FIELD.ALLOWED_TOOLS,
  CONFIGURATION_FIELD.ASK_FIRST_TOOLS,
]
// A remote update must not split a pending linked choice.
const LINKED_FIELDS = [MODEL_FIELDS, TOOL_FIELDS]
// The tools an Agent can be allowed to call are listed with its configuration.
const CONFIGURATION_FIELDS = [
  ...REQUIRED_FIELDS,
  CONFIGURATION_FIELD.REASONING_EFFORT,
  CONFIGURATION_FIELD.APPLIED_REASONING_EFFORT,
  CONFIGURATION_FIELD.RUN_AS,
  ...TOOL_FIELDS,
  CONFIGURATION_FIELD.AVAILABLE_TOOLS,
  CONFIGURATION_FIELD.WEB_SEARCH_ENABLED,
  CONFIGURATION_FIELD.WEB_SEARCH_AVAILABLE,
  CONFIGURATION_FIELD.WEB_SEARCH_BLOCKED_BY_TOOLS,
  CONFIGURATION_FIELD.AVAILABLE_TRIGGER_TYPES,
]

const emptyConfiguration = () => ({
  instructions: '',
  provider_type: null,
  model_identifier: null,
  reasoning_effort: null,
  applied_reasoning_effort: null,
  run_as: null,
  allowed_tools: [],
  ask_first_tools: [],
  available_tools: [],
  web_search_enabled: false,
  web_search_available: false,
  web_search_blocked_by_tools: false,
  available_trigger_types: [],
})

/** Identities match by type and id, and tool lists by their names. */
const isSameValue = (field, a, b) => {
  if (field === CONFIGURATION_FIELD.RUN_AS)
    return a?.type === b?.type && a?.id === b?.id
  if (TOOL_FIELDS.includes(field)) {
    return a?.length === b?.length && a.every((name) => b.includes(name))
  }
  return a === b
}

/** Page-local Agent configuration, kept out of the shared application store. */
export function useAgentConfiguration(agent) {
  const store = useStore()
  const { $client, $hasPermission, $i18n } = useNuxtApp()
  const service = AgentApplicationService($client)
  const applicationService = ApplicationService($client)
  const permission = (operation) =>
    Boolean(
      agent.value &&
      $hasPermission(operation, agent.value, agent.value.workspace.id)
    )

  const canReadConfiguration = computed(() =>
    permission('agent_application.read_configuration')
  )
  const canUpdateConfiguration = computed(
    () => canReadConfiguration.value && permission('application.update')
  )

  const name = ref(agent.value?.name ?? '')
  const savingName = ref(false)
  const readiness = computed(() => {
    if (canReadConfiguration.value && savedConfiguration.value) {
      const errors = Object.values(fieldErrors.value)
      return errors.includes(CONFIGURATION_ERROR.REQUIRED)
        ? AGENT_READINESS.INCOMPLETE
        : errors.length
          ? AGENT_READINESS.UNAVAILABLE
          : AGENT_READINESS.READY
    }
    return agent.value?.readiness ?? null
  })
  const readinessError = ref(false)
  // The first load starts on mount, so the server renders the same pending state.
  const availabilityLoading = ref(canReadConfiguration.value)
  const availabilityError = ref(false)
  const configuration = reactive(emptyConfiguration())
  const savedConfiguration = ref(null)
  const configurationLoaded = computed(() => savedConfiguration.value !== null)
  const configurationErrors = ref({})
  const configurationLoading = ref(canReadConfiguration.value)
  const configurationLoadError = ref(false)
  const pendingConfiguration = reactive({})
  const savingConfiguration = ref(false)
  const configurationSaveError = ref(false)

  let scope = 0
  let readinessRequest = 0
  let availabilityRequest = 0
  let configurationRequest = 0
  let refreshPending = false
  let refreshPendingRecovery = false
  let inFlightConfiguration = {}
  let configurationSavePromise = null
  let nameSavePromise = null

  const workspace = computed(() =>
    agent.value
      ? store.getters['workspace/get'](agent.value.workspace.id)
      : null
  )
  const enabledModels = computed(() =>
    getEnabledModelsForAIProviderFeature(workspace.value, 'ai_agent')
  )
  const hasPendingConfiguration = computed(
    () => Object.keys(pendingConfiguration).length > 0
  )
  const fieldErrors = computed(() => {
    const saved = savedConfiguration.value
    if (!canReadConfiguration.value || !saved) return {}

    const errors = {}
    for (const field of REQUIRED_FIELDS) {
      if (!(configuration[field] || '').trim()) {
        errors[field] = CONFIGURATION_ERROR.REQUIRED
      } else if (
        configurationErrors.value[field] === CONFIGURATION_ERROR.UNAVAILABLE &&
        configuration[field] === saved[field] &&
        (field !== CONFIGURATION_FIELD.MODEL_IDENTIFIER ||
          configuration.provider_type === saved.provider_type)
      ) {
        // The backend's error outranks an older cached model list.
        errors[field] = CONFIGURATION_ERROR.UNAVAILABLE
      }
    }
    if (!availabilityLoading.value && !availabilityError.value) {
      const provider = configuration.provider_type
      const models = enabledModels.value[provider] || []
      if (provider && !models.length)
        errors.provider_type = CONFIGURATION_ERROR.UNAVAILABLE
      if (
        provider &&
        configuration.model_identifier &&
        !models.includes(configuration.model_identifier)
      ) {
        errors.model_identifier = CONFIGURATION_ERROR.UNAVAILABLE
      }
    }
    return errors
  })
  const readyToSend = computed(
    () =>
      readiness.value === AGENT_READINESS.READY &&
      !readinessError.value &&
      !availabilityLoading.value &&
      !availabilityError.value &&
      !savingConfiguration.value &&
      (!canReadConfiguration.value ||
        (!configurationLoading.value &&
          !configurationLoadError.value &&
          !hasPendingConfiguration.value &&
          !configurationSaveError.value &&
          !Object.keys(fieldErrors.value).length))
  )
  const scopeIsCurrent = (currentScope) => scope === currentScope

  function updateApplication(data) {
    return store.dispatch('application/forceUpdate', {
      application: agent.value,
      data,
    })
  }

  async function renameAgent() {
    if (!canUpdateConfiguration.value) return true
    if (savingName.value) {
      return nameSavePromise.then((saved) => saved && renameAgent())
    }
    const trimmed = name.value.trim()
    if (!trimmed || trimmed === agent.value.name) {
      name.value = agent.value.name
      return true
    }
    const currentScope = scope
    const application = agent.value
    const previousName = application.name
    const submittedName = name.value
    savingName.value = true
    // Use the normal application rename, with the same optimistic value in all
    // navigation and headings while the request is in flight.
    updateApplication({ name: trimmed })
    nameSavePromise = (async () => {
      try {
        await store.dispatch('application/update', {
          application,
          values: { name: trimmed },
        })
        if (scopeIsCurrent(currentScope) && name.value === submittedName) {
          name.value = application.name
        }
        return true
      } catch (error) {
        if (application.name === trimmed) {
          await store.dispatch('application/forceUpdate', {
            application,
            data: { name: previousName },
          })
        }
        if (scopeIsCurrent(currentScope) && name.value === submittedName) {
          name.value = application.name
        }
        notifyIf(error, 'application')
        return false
      } finally {
        if (scopeIsCurrent(currentScope)) savingName.value = false
      }
    })()
    return nameSavePromise
  }

  async function fetchAgentReadiness() {
    if (!agent.value) return
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++readinessRequest
    readinessError.value = false
    try {
      // Use the ordinary application read so agent_loaded stays once per visit.
      const { data } = await applicationService.get(agentId)
      if (scopeIsCurrent(currentScope) && request === readinessRequest) {
        await updateApplication({ readiness: data.readiness })
      }
    } catch {
      if (scopeIsCurrent(currentScope) && request === readinessRequest) {
        readinessError.value = true
      }
    }
  }

  async function fetchAvailability() {
    if (!canReadConfiguration.value) return
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

  function applyConfiguration(data) {
    const empty = emptyConfiguration()
    const saved = Object.fromEntries(
      CONFIGURATION_FIELDS.map((field) => [field, data[field] ?? empty[field]])
    )
    savedConfiguration.value = saved
    for (const fields of LINKED_FIELDS) {
      if (fields.some((field) => field in pendingConfiguration)) {
        for (const field of fields) {
          if (!isSameValue(field, configuration[field], saved[field])) {
            pendingConfiguration[field] = configuration[field]
          }
        }
      }
    }
    for (const field of CONFIGURATION_FIELDS) {
      if (!(field in pendingConfiguration)) configuration[field] = saved[field]
      if (isSameValue(field, configuration[field], saved[field])) {
        delete pendingConfiguration[field]
      }
    }
    if (
      APPLIED_REASONING_EFFORT_INPUTS.some(
        (field) => field in pendingConfiguration
      )
    ) {
      configuration.applied_reasoning_effort = undefined
    }
    configurationErrors.value = data.errors || {}
    ++readinessRequest
    readinessError.value = false
    // Keep only public metadata in the shared application store.
    updateApplication({ readiness: data.readiness })
  }

  async function fetchConfiguration(realtimeRecovery = false) {
    if (!canReadConfiguration.value) return
    if (savingConfiguration.value) {
      refreshPending = true
      refreshPendingRecovery ||= realtimeRecovery
      return
    }
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++configurationRequest
    configurationLoading.value = !savedConfiguration.value
    configurationLoadError.value = false
    try {
      const { data } = await service.getConfiguration(agentId, realtimeRecovery)
      if (
        scopeIsCurrent(currentScope) &&
        request === configurationRequest &&
        canReadConfiguration.value
      ) {
        applyConfiguration(data)
      }
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

  function updateConfiguration(values) {
    if (!canUpdateConfiguration.value) return
    for (const [field, value] of Object.entries(values)) {
      if (!CONFIGURATION_FIELDS.includes(field)) continue
      const normalized = MODEL_FIELDS.includes(field) && !value ? null : value
      if (
        APPLIED_REASONING_EFFORT_INPUTS.includes(field) &&
        configuration[field] !== normalized
      ) {
        configuration.applied_reasoning_effort = undefined
      }
      configuration[field] = normalized
      if (
        isSameValue(field, savedConfiguration.value?.[field], normalized) &&
        !(field in inFlightConfiguration)
      ) {
        delete pendingConfiguration[field]
      } else {
        pendingConfiguration[field] = normalized
      }
    }
    configurationSaveError.value = false
  }

  function saveConfiguration() {
    // A blur during a save commits its edit once that save finishes.
    if (savingConfiguration.value) {
      return configurationSavePromise.then(saveConfiguration)
    }
    if (!canUpdateConfiguration.value || !hasPendingConfiguration.value) {
      return false
    }
    const currentScope = scope
    const agentId = agent.value.id
    const values = { ...pendingConfiguration }
    if (TOOL_FIELDS.some((field) => field in values)) {
      // The backend reads both lists together and defaults omitted ask-first ones.
      for (const field of TOOL_FIELDS) values[field] = configuration[field]
    }
    savingConfiguration.value = true
    inFlightConfiguration = values
    configurationSaveError.value = false
    ++configurationRequest
    configurationSavePromise = (async () => {
      let rejectedIdentity = false
      try {
        const { data } = await service.updateConfiguration(agentId, values)
        if (!scopeIsCurrent(currentScope) || !canReadConfiguration.value) {
          return false
        }
        for (const field of Object.keys(values)) {
          if (configuration[field] === values[field]) {
            delete pendingConfiguration[field]
          }
        }
        applyConfiguration(data)
        return true
      } catch (error) {
        if (scopeIsCurrent(currentScope) && canReadConfiguration.value) {
          if (
            error.response?.data?.error ===
              API_ERROR_CODE.AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST &&
            Object.hasOwn(values, CONFIGURATION_FIELD.RUN_AS)
          ) {
            // A domain rejection confirms that none of this PATCH was saved.
            // Roll back only that submitted choice; newer edits remain pending.
            if (
              isSameValue(
                CONFIGURATION_FIELD.RUN_AS,
                configuration.run_as,
                values.run_as
              )
            ) {
              configuration.run_as = savedConfiguration.value?.run_as ?? null
              delete pendingConfiguration.run_as
              store.dispatch('toast/error', {
                title: $i18n.t('agent.runAsRejectedTitle'),
                message: $i18n.t('agent.runAsRejected'),
              })
            }
            rejectedIdentity = true
            refreshPending = true
            refreshPendingRecovery = true
            return CONFIGURATION_SAVE_RESULT.REJECTED_IDENTITY
          }
          configurationSaveError.value = true
        }
        return false
      } finally {
        if (scopeIsCurrent(currentScope)) {
          if (!canReadConfiguration.value) fetchAgentReadiness()
          savingConfiguration.value = false
          inFlightConfiguration = {}
          if (
            refreshPending &&
            !(rejectedIdentity && hasPendingConfiguration.value)
          ) {
            const realtimeRecovery = refreshPendingRecovery
            refreshPending = false
            refreshPendingRecovery = false
            fetchConfiguration(realtimeRecovery)
          }
        }
      }
    })().then((result) => {
      if (
        result === CONFIGURATION_SAVE_RESULT.REJECTED_IDENTITY &&
        scopeIsCurrent(currentScope)
      ) {
        // Other fields in the rejected PATCH still need saving. Do not make the
        // user retry them together with a selection the server has refused.
        return hasPendingConfiguration.value ? saveConfiguration() : false
      }
      return result
    })
    return configurationSavePromise
  }

  async function flushConfiguration() {
    const currentScope = scope
    if (!(await renameAgent())) return false
    while (scopeIsCurrent(currentScope) && hasPendingConfiguration.value) {
      const saved = await saveConfiguration()
      if (!saved || configurationSaveError.value) break
    }
    return !scopeIsCurrent(currentScope) || !hasPendingConfiguration.value
  }

  onBeforeRouteLeave(flushConfiguration)
  onBeforeRouteUpdate(async (to, from) => {
    if (await flushConfiguration()) return true
    // Page middleware selects the next Agent before update guards run.
    await selectAgentApplication(useNuxtApp(), from)
    return false
  })

  async function refreshConfiguration({ refreshAgent = true } = {}) {
    await Promise.all([
      refreshAgent && fetchAgentReadiness(),
      fetchAvailability(),
      fetchConfiguration(),
    ])
  }

  function clearConfiguration() {
    ++configurationRequest
    Object.assign(configuration, emptyConfiguration())
    savedConfiguration.value = null
    configurationErrors.value = {}
    configurationLoading.value = false
    Object.keys(pendingConfiguration).forEach(
      (field) => delete pendingConfiguration[field]
    )
    configurationSaveError.value = false
  }

  function reset() {
    refreshRunAs.cancel()
    ++scope
    name.value = agent.value?.name ?? ''
    clearConfiguration()
    readinessError.value = false
    availabilityLoading.value = false
    availabilityError.value = false
    configurationLoadError.value = false
    savingConfiguration.value = false
    inFlightConfiguration = {}
    configurationSavePromise = null
    nameSavePromise = null
    savingName.value = false
    refreshPending = false
    refreshPendingRecovery = false
  }

  onMounted(() => refreshConfiguration({ refreshAgent: false }))
  watch([() => agent.value?.id, () => store.state.auth.user?.id], () => {
    reset()
    if (agent.value) refreshConfiguration({ refreshAgent: false })
  })
  watch(
    () => agent.value?.name,
    (value, previous) => {
      // Remote renames update clean inputs, while a local name draft stays put.
      if (name.value === previous) name.value = value ?? ''
    }
  )
  watch(
    () => agent.value?._?.realtimeVersion,
    () => fetchConfiguration(true)
  )
  const refreshRunAs = debounce(() => fetchConfiguration(true), 100, {
    maxWait: 500,
  })
  watch(() => agent.value?._?.runAsIdentityVersion || 0, refreshRunAs)
  watch(
    () => JSON.stringify(enabledModels.value),
    () => {
      fetchAgentReadiness()
      fetchConfiguration(true)
    }
  )
  watch(canReadConfiguration, (allowed) => {
    if (allowed) {
      fetchAvailability()
      fetchConfiguration(true)
    } else {
      ++availabilityRequest
      availabilityLoading.value = false
      availabilityError.value = false
      clearConfiguration()
      fetchAgentReadiness()
    }
  })
  onBeforeUnmount(reset)

  return {
    canReadConfiguration,
    canUpdateConfiguration,
    name,
    savingName,
    readiness,
    readinessError,
    availabilityLoading,
    availabilityError,
    enabledModels,
    configuration,
    fieldErrors,
    configurationLoading,
    configurationLoaded,
    configurationLoadError,
    savingConfiguration,
    configurationSaveError,
    readyToSend,
    renameAgent,
    updateConfiguration,
    saveConfiguration,
    fetchConfiguration,
    refreshConfiguration,
  }
}
