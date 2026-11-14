import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import cloneDeep from 'lodash/cloneDeep'
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import { removeActionInputReferences } from '@baserow/modules/agent/utils/actionFormulas'
import AgentActionService from '@baserow/modules/agent/services/agentActions'
import { actionFieldLabel } from '@baserow/modules/agent/utils/actionLabels'
import { notifyIf } from '@baserow/modules/core/utils/error'

const EDITABLE_FIELDS = [
  'name',
  'description',
  'inputs',
  'enabled',
  'ask_first',
]
const missing = (error) =>
  error.response?.data?.error === 'ERROR_AGENT_ACTION_DOES_NOT_EXIST'

/** Page-local drafts, with one serialized save per independently configured action. */
export function useAgentActions(agent) {
  const { $client, $registry } = useNuxtApp()
  const { t } = useI18n()
  const store = useStore()
  const service = AgentActionService($client)
  const actions = ref([])
  const loading = ref(false)
  const loadError = ref(false)
  const savingIds = reactive(new Set())
  const saveErrors = reactive({})
  const saved = new Map()
  let scope = 0
  let request = 0

  function track(action) {
    const entry = {
      agentId: agent.value.id,
      data: cloneDeep(action),
      busy: false,
    }
    // The list renders this same proxy, so what a save returns shows in the card.
    const draft = reactive(action)
    entry.schedule = debounce(() => flush(draft, null, entry), 500)
    saved.set(action.id, entry)
  }

  function forget(id, keepSaving = false) {
    const entry = saved.get(id)
    if (entry) {
      entry.cancelled = !keepSaving
      entry.schedule.cancel()
    }
    saved.delete(id)
    delete saveErrors[id]
    savingIds.delete(id)
  }

  function remove(id) {
    forget(id)
    actions.value = actions.value.filter((action) => action.id !== id)
  }

  function changes(action, baseline = saved.get(action.id)?.data) {
    if (!baseline) return {}
    const changed = Object.fromEntries(
      EDITABLE_FIELDS.filter((key) => !isEqual(action[key], baseline[key])).map(
        (key) => [key, cloneDeep(action[key])]
      )
    )
    const serviceValues = Object.fromEntries(
      Object.entries(action.service).filter(
        ([key, value]) => !isEqual(value, baseline.service[key])
      )
    )
    if (Object.keys(serviceValues).length)
      changed.service = cloneDeep(serviceValues)
    return changed
  }

  // Retain edits made after a request began, or before another editor's event.
  function adopt(
    action,
    data,
    baseline = saved.get(action.id)?.data,
    entry = saved.get(action.id)
  ) {
    if (!entry) return
    const draft = changes(action, baseline)
    Object.assign(action, data, draft, {
      service: { ...data.service, ...draft.service },
    })
    entry.data = cloneDeep(data)
  }

  async function fetchActions({ integrations = false } = {}) {
    if (!agent.value?.id) return
    const currentScope = scope
    const currentRequest = ++request
    const isCurrent = () => currentScope === scope && currentRequest === request
    const application = agent.value
    loading.value = true
    loadError.value = false
    try {
      if (integrations)
        await store.dispatch('integration/fetch', { application })
      const { data } = await service.list(application.id)
      if (!isCurrent()) return
      const existing = new Map(
        actions.value.map((action) => [action.id, action])
      )
      actions.value = data.map((action) => {
        const current = existing.get(action.id)
        if (current) {
          adopt(current, action)
          return current
        }
        track(action)
        return action
      })
      for (const id of saved.keys()) {
        if (!data.some((action) => action.id === id)) forget(id)
      }
    } catch {
      if (isCurrent()) loadError.value = true
    } finally {
      if (isCurrent()) loading.value = false
    }
  }

  async function createAction(type) {
    const currentScope = scope
    try {
      const { data } = await service.create(agent.value.id, { type })
      if (currentScope !== scope) return
      const existing = actions.value.find((action) => action.id === data.id)
      if (existing) adopt(existing, data)
      else {
        track(data)
        actions.value.push(data)
      }
      return data
    } catch (error) {
      notifyIf(error, 'action')
    }
  }

  async function flush(action, fields = null, entry = saved.get(action.id)) {
    if (!entry || entry.cancelled) return
    const isCurrent = () => saved.get(action.id) === entry
    if (entry.busy) {
      entry.changedWhileSaving = true
      return
    }
    const pending = changes(action, entry.data)
    // A draft changed back to what is saved has nothing left to be rejected.
    if (!Object.keys(pending).length && isCurrent())
      delete saveErrors[action.id]
    const sent = Object.fromEntries(
      Object.entries(pending).filter(([key]) => !fields || fields.includes(key))
    )
    if (!Object.keys(sent).length) return
    const baseline = {
      ...cloneDeep(entry.data),
      ...sent,
      service: { ...entry.data.service, ...sent.service },
    }
    entry.busy = true
    if (isCurrent()) savingIds.add(action.id)
    try {
      const { data } = await service.update(entry.agentId, action.id, sent)
      if (entry.cancelled) return
      // Navigation detaches the card, but its last edits still belong to this save.
      adopt(action, data, baseline, entry)
      if (isCurrent() && !Object.keys(changes(action)).length)
        delete saveErrors[action.id]
    } catch (error) {
      if (entry.cancelled) return
      if (missing(error)) {
        entry.cancelled = true
        if (isCurrent()) remove(action.id)
      } else if (!isCurrent()) {
        notifyIf(error, 'action')
      } else {
        // Keep rejected drafts visible so they can be repaired without retyping.
        const validation =
          error.response?.data?.error === 'ERROR_REQUEST_BODY_VALIDATION'
        const detail = error.response?.data?.detail
        const messages = (value) => {
          if (typeof value === 'string') return [value]
          if (!value || typeof value !== 'object') return []
          if (typeof value.error === 'string') return [value.error]
          return Object.values(value).flatMap(messages)
        }
        saveErrors[action.id] =
          validation && detail && typeof detail === 'object'
            ? Object.entries(detail)
                .map(
                  ([field, errors]) =>
                    `${actionFieldLabel($registry, action.type, field, t)}: ${messages(errors).join(' ')}`
                )
                .join(' ')
            : t('agent.actionSaveError')
        if (!validation) notifyIf(error, 'action')
      }
    } finally {
      entry.busy = false
      if (saved.get(action.id) === entry) savingIds.delete(action.id)
    }
    if (entry.changedWhileSaving) {
      entry.changedWhileSaving = false
      flush(action, null, entry)
    }
  }

  function updateAction(action, values) {
    const entry = saved.get(action.id)
    if (!entry) return
    if (values.inputs) {
      const remaining = new Set(values.inputs.map(({ id }) => id))
      const removed = action.inputs
        .filter(({ id }) => !remaining.has(id))
        .map(({ id }) => id)
      if (removed.length)
        values = {
          ...values,
          service: removeActionInputReferences(
            { ...action.service, ...values.service },
            removed
          ),
        }
    }
    const previousService = action.service
    Object.assign(action, cloneDeep(values))
    if (values.service)
      action.service = { ...previousService, ...values.service }
    const immediate = ['enabled', 'ask_first'].filter(
      (field) => field in values
    )
    if (immediate.length) flush(action, immediate)
    else entry.schedule()
  }

  async function deleteAction(action) {
    const entry = saved.get(action.id)
    if (!entry) return
    entry.schedule.cancel()
    try {
      await service.delete(entry.agentId, action.id)
      if (saved.get(action.id) === entry) remove(action.id)
    } catch (error) {
      if (missing(error) && saved.get(action.id) === entry) remove(action.id)
      else notifyIf(error, 'action')
    }
  }

  function flushScheduledSaves() {
    for (const entry of saved.values()) entry.schedule.flush()
  }

  onMounted(() => fetchActions({ integrations: true }))
  watch(
    () => agent.value?.id,
    () => {
      flushScheduledSaves()
      ++scope
      for (const id of saved.keys()) forget(id, true)
      actions.value = []
      fetchActions({ integrations: true })
    }
  )
  watch(
    () => agent.value?._?.actionUpdate,
    (event) => {
      if (!event) return
      if (event.kind === 'deleted') remove(event.actionId)
      else {
        const existing = actions.value.find(
          (action) => action.id === event.action.id
        )
        if (existing) adopt(existing, event.action)
        else {
          track(event.action)
          actions.value.push(event.action)
        }
      }
    }
  )
  // Editing a connection can repair an unconfigured action without changing it.
  watch(
    () => store.state.integration.generation[agent.value?.id],
    () => {
      if (!loading.value) fetchActions()
    }
  )
  onBeforeUnmount(flushScheduledSaves)

  return {
    actions,
    loading,
    loadError,
    savingIds,
    saveErrors,
    fetchActions,
    createAction,
    updateAction,
    deleteAction,
    flush,
  }
}
