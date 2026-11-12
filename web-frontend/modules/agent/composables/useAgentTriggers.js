import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import cloneDeep from 'lodash/cloneDeep'
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentTriggerService from '@baserow/modules/agent/services/agentTriggers'
import { API_ERROR_CODE } from '@baserow/modules/agent/constants'
import { defaultTriggerMessage } from '@baserow/modules/agent/utils/triggers'

const TYPED_SAVE_DELAY = 500
const TRIGGER_FIELDS = ['name', 'enabled', 'message']
const PICKED_FIELDS = ['name', 'enabled']

/**
 * @param {object} trigger A trigger as the server returned it.
 * @returns {object} The values a card edits, as the server holds them.
 */
const savedValuesOf = (trigger) =>
  cloneDeep({
    ...Object.fromEntries(
      TRIGGER_FIELDS.map((field) => [field, trigger[field]])
    ),
    service: trigger.service,
  })

/**
 * Page-local trigger list of one Agent. Cards show their edits at once, and each
 * trigger saves the difference from what the server holds, one request at a
 * time, so a rejected or slow save never loses or reverts a newer edit.
 *
 * @param {import('vue').Ref<object>} agent The Agent whose triggers are listed.
 * @returns {object} The triggers, their loading and saving state, and actions.
 */
export function useAgentTriggers(agent) {
  const { $client, $registry } = useNuxtApp()
  const { t } = useI18n()
  const service = AgentTriggerService($client)
  const triggers = ref([])
  const loading = ref(false)
  const loadError = ref(false)
  const savingIds = reactive(new Set())
  const serviceErrors = reactive({})
  // Per trigger id: the server's values and the Agent they belong to.
  const saved = new Map()
  const scheduledSaves = new Map()
  const inFlight = new Set()
  const editedWhileSaving = new Set()
  let scope = 0
  let listRequest = 0

  const agentId = () => agent.value?.id
  const scopeIsCurrent = (currentScope) => scope === currentScope
  const errorCode = (error) => error.response?.data?.error

  function track(trigger) {
    saved.set(trigger.id, {
      agentId: agentId(),
      values: savedValuesOf(trigger),
    })
  }

  function forget(triggerId) {
    scheduledSaves.get(triggerId)?.cancel()
    scheduledSaves.delete(triggerId)
    saved.delete(triggerId)
    delete serviceErrors[triggerId]
  }

  function removeTrigger(trigger) {
    forget(trigger.id)
    triggers.value = triggers.value.filter((item) => item !== trigger)
  }

  /** Loads the triggers, ignoring a reply that a newer load or reset replaced. */
  async function fetchTriggers() {
    if (!agentId()) return
    const currentScope = scope
    const request = ++listRequest
    const isCurrent = () =>
      scopeIsCurrent(currentScope) && request === listRequest
    loading.value = true
    loadError.value = false
    try {
      const { data } = await service.list(agentId())
      if (!isCurrent()) return
      data.forEach(track)
      triggers.value = data
    } catch {
      if (isCurrent()) loadError.value = true
    } finally {
      if (isCurrent()) loading.value = false
    }
  }

  /**
   * Creates a trigger of the given type with the type's defaults and the default
   * opening message.
   *
   * @param {string} type The service type of the trigger.
   * @returns {Promise<object|null>} The created trigger, or null when it failed.
   */
  async function createTrigger(type) {
    const currentScope = scope
    const serviceType = $registry.get('service', type)
    const defaults = serviceType.getDefaultValues(null, {})
    try {
      const { data } = await service.create(agentId(), {
        type,
        message: defaultTriggerMessage(t, serviceType),
        service: defaults,
      })
      if (scopeIsCurrent(currentScope)) {
        track(data)
        triggers.value.push(data)
      }
      return data
    } catch (error) {
      notifyIf(error, 'trigger')
      return null
    }
  }

  /**
   * @param {object} trigger A tracked trigger, as its card shows it.
   * @returns {object} What the card shows that the server doesn't hold, with
   *   service values compared field by field.
   */
  function unsavedValues(trigger) {
    const { values } = saved.get(trigger.id)
    const unsaved = Object.fromEntries(
      TRIGGER_FIELDS.filter(
        (field) => !isEqual(trigger[field], values[field])
      ).map((field) => [field, trigger[field]])
    )
    const serviceValues = Object.fromEntries(
      Object.entries(trigger.service).filter(
        ([field, value]) => !isEqual(value, values.service[field])
      )
    )
    if (Object.keys(serviceValues).length) {
      unsaved.service = { type: trigger.service.type, ...serviceValues }
    }
    return unsaved
  }

  /**
   * Sends what a trigger's card shows that the server doesn't hold, unless a
   * save of it is already in flight: that one saves again once it ends.
   *
   * @param {object} trigger The trigger to save.
   * @param {string[]|null} fields The fields to send, or null for all of them.
   */
  async function flush(trigger, fields = null) {
    const entry = saved.get(trigger.id)
    if (!entry) return
    if (inFlight.has(trigger.id)) {
      editedWhileSaving.add(trigger.id)
      return
    }
    const sent = Object.fromEntries(
      Object.entries(unsavedValues(trigger)).filter(
        ([field]) => !fields || fields.includes(field)
      )
    )
    if (!Object.keys(sent).length) return
    const currentScope = scope
    inFlight.add(trigger.id)
    savingIds.add(trigger.id)
    try {
      const { data } = await service.update(entry.agentId, trigger.id, sent)
      if (!scopeIsCurrent(currentScope)) return
      if (sent.service) delete serviceErrors[trigger.id]
      adoptSaved(trigger, sent, data)
    } catch (error) {
      if (scopeIsCurrent(currentScope)) handleSaveError(trigger, sent, error)
    } finally {
      inFlight.delete(trigger.id)
      savingIds.delete(trigger.id)
    }
    if (editedWhileSaving.delete(trigger.id)) flush(trigger)
  }

  /**
   * Takes the server's reply as saved, and shows its values where the card still
   * shows what was sent: a field edited meanwhile keeps the newer edit.
   *
   * @param {object} trigger The saved trigger.
   * @param {object} sent The values that were sent.
   * @param {object} data The trigger the server returned.
   */
  function adoptSaved(trigger, sent, data) {
    const entry = saved.get(trigger.id)
    if (!entry) return
    const previous = entry.values
    const latest = savedValuesOf(data)
    const shows = (value, field, base) =>
      isEqual(value, field in sent ? sent[field] : base)
    for (const field of TRIGGER_FIELDS) {
      if (shows(trigger[field], field, previous[field])) {
        trigger[field] = latest[field]
      }
    }
    const sentService = sent.service || {}
    trigger.service = Object.fromEntries(
      Object.entries({ ...trigger.service, ...latest.service }).map(
        ([field, value]) => {
          const showsSaved = isEqual(
            trigger.service[field],
            field in sentService ? sentService[field] : previous.service[field]
          )
          return [field, showsSaved ? value : trigger.service[field]]
        }
      )
    )
    entry.values = latest
  }

  /**
   * Keeps rejected service values shown with their error, to be sent again with
   * the next edit; otherwise shows the server's values again for what failed.
   *
   * @param {object} trigger The trigger whose save failed.
   * @param {object} sent The values that were sent.
   * @param {Error} error The failure.
   */
  function handleSaveError(trigger, sent, error) {
    const code = errorCode(error)
    const { values } = saved.get(trigger.id) || {}
    if (code === API_ERROR_CODE.TRIGGER_SERVICE_MISCONFIGURED) {
      const detail = error.response.data.detail
      serviceErrors[trigger.id] =
        typeof detail === 'string' ? detail : t('agent.triggerMisconfigured')
      return
    }
    if (code === API_ERROR_CODE.AGENT_TRIGGER_DOES_NOT_EXIST) {
      removeTrigger(trigger)
      return
    }
    notifyIf(error, 'trigger')
    if (!values) return
    for (const field of TRIGGER_FIELDS) {
      if (field in sent && isEqual(trigger[field], sent[field])) {
        trigger[field] = values[field]
      }
    }
    if (sent.service) {
      const reverted = { ...trigger.service }
      for (const [field, value] of Object.entries(sent.service)) {
        if (isEqual(trigger.service[field], value)) {
          reverted[field] = values.service[field]
        }
      }
      trigger.service = reverted
    }
  }

  function scheduleSave(trigger) {
    if (!scheduledSaves.has(trigger.id)) {
      scheduledSaves.set(
        trigger.id,
        debounce(() => flush(trigger), TYPED_SAVE_DELAY)
      )
    }
    scheduledSaves.get(trigger.id)()
  }

  /**
   * Shows a card's edit at once and saves it: a name or a switch right away and
   * alone, so rejected settings can't block it, typed values with everything
   * unsaved once typing pauses.
   *
   * @param {object} trigger The trigger the card shows.
   * @param {object} values The edited `name`, `enabled`, `message` or service
   *   values.
   */
  function updateTrigger(trigger, values) {
    if (!saved.has(trigger.id)) return
    for (const field of TRIGGER_FIELDS) {
      if (field in values) trigger[field] = values[field]
    }
    if (values.service) {
      trigger.service = { ...trigger.service, ...values.service }
    }
    const picked = PICKED_FIELDS.filter((field) => field in values)
    if (picked.length) {
      flush(trigger, picked)
    } else {
      scheduleSave(trigger)
    }
  }

  /**
   * Removes the trigger at once and trashes it; it comes back if that fails,
   * unless it was already gone.
   *
   * @param {object} trigger The trigger to delete.
   */
  async function deleteTrigger(trigger) {
    const currentScope = scope
    const index = triggers.value.indexOf(trigger)
    if (index === -1) return
    const entry = saved.get(trigger.id)
    scheduledSaves.get(trigger.id)?.cancel()
    triggers.value.splice(index, 1)
    try {
      await service.delete(entry?.agentId ?? agentId(), trigger.id)
    } catch (error) {
      if (!scopeIsCurrent(currentScope)) return
      if (errorCode(error) !== API_ERROR_CODE.AGENT_TRIGGER_DOES_NOT_EXIST) {
        triggers.value.splice(index, 0, trigger)
        notifyIf(error, 'trigger')
        return
      }
    }
    forget(trigger.id)
  }

  function flushScheduledSaves() {
    for (const scheduled of scheduledSaves.values()) scheduled.flush()
  }

  function reset() {
    flushScheduledSaves()
    for (const triggerId of [...saved.keys()]) forget(triggerId)
    ++scope
    triggers.value = []
    loading.value = false
    loadError.value = false
    savingIds.clear()
    inFlight.clear()
    editedWhileSaving.clear()
  }

  onMounted(fetchTriggers)
  watch(
    () => agent.value?.id,
    () => {
      reset()
      fetchTriggers()
    }
  )
  onBeforeUnmount(flushScheduledSaves)

  return {
    triggers,
    loading,
    loadError,
    savingIds,
    serviceErrors,
    fetchTriggers,
    createTrigger,
    updateTrigger,
    deleteTrigger,
  }
}
