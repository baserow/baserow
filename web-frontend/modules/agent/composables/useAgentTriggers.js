import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import cloneDeep from 'lodash/cloneDeep'
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentTriggerService from '@baserow/modules/agent/services/agentTriggers'
import { API_ERROR_CODE } from '@baserow/modules/agent/constants'
import {
  newTriggerMessage,
  newTriggerValues,
  serviceTypeOf,
} from '@baserow/modules/agent/utils/triggers'
import { getRunAsStatus } from '@baserow/modules/agent/utils/runAs'

const TYPED_SAVE_DELAY = 500
const TRIGGER_FIELDS = [
  'type',
  'name',
  'enabled',
  'message',
  'on_overlap',
  'batch_size',
]
const PICKED_FIELDS = ['type', 'name', 'enabled', 'on_overlap']
const SAVED_FIELDS = [...TRIGGER_FIELDS, 'service']
const TYPE_CHANGE_FIELDS = ['type', 'service', 'message']

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
 * edited field is saved in a request of its own, one at a time per trigger, so a
 * rejected value never holds back another field and a slow save never reverts a
 * newer edit. What each trigger type's form may choose from is loaded for the
 * Agent's run identity, and again whenever that identity changes.
 *
 * @param {import('vue').Ref<object>} agent The Agent whose triggers are listed.
 * @param {Function} getRunAs Returns the Agent's configured run identity, or
 *   null.
 * @returns {object} The triggers, their loading and saving state, the options
 *   of each trigger type with a counter that changes whenever they reload,
 *   whether either failed to load, and actions.
 */
export function useAgentTriggers(agent, getRunAs = () => null) {
  const { $client, $registry } = useNuxtApp()
  const { t } = useI18n()
  const service = AgentTriggerService($client)
  const triggers = ref([])
  // By type: its form choices and default overlap rule; null while loading.
  const triggerTypes = ref(null)
  const typesVersion = ref(0)
  const loading = ref(false)
  const loadError = ref(false)
  const typesLoadError = ref(false)
  const savingIds = reactive(new Set())
  const deletingIds = reactive(new Set())
  const serviceErrors = reactive({})
  // Per trigger id: how often a failed save reverted its service values.
  const serviceReverts = reactive({})
  // Per trigger id: the server's values and the Agent they belong to.
  const saved = new Map()
  const scheduledSaves = new Map()
  // Per trigger id: the typed fields waiting for the typing to pause.
  const typedFields = new Map()
  // Per trigger id: the fields due to be sent.
  const dueFields = new Map()
  const inFlight = new Set()
  const refusedSwitchOns = new Set()
  let scope = 0
  let listRequest = 0
  let typesRequest = 0

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
    typedFields.delete(triggerId)
    dueFields.delete(triggerId)
    saved.delete(triggerId)
    refusedSwitchOns.delete(triggerId)
    delete serviceErrors[triggerId]
    delete serviceReverts[triggerId]
  }

  /**
   * @param {Map<number, Set<string>>} fieldsByTrigger The fields per trigger id.
   * @param {number} triggerId The trigger the fields belong to.
   * @param {Iterable<string>} fields The fields to add.
   */
  function addFields(fieldsByTrigger, triggerId, fields) {
    const added = fieldsByTrigger.get(triggerId) || new Set()
    fields.forEach((field) => added.add(field))
    fieldsByTrigger.set(triggerId, added)
  }

  /**
   * @param {number} triggerId The trigger to save.
   * @returns {string|undefined} The next due field, no longer due, if any.
   */
  function takeDueField(triggerId) {
    const due = dueFields.get(triggerId)
    const field = SAVED_FIELDS.find((name) => due?.has(name))
    due?.delete(field)
    return field
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
   * Loads what each trigger type's form may choose from for the Agent's run
   * identity, ignoring a reply that a newer load or reset replaced. When it
   * fails, the forms still open, with nothing to choose from until a retry.
   */
  async function fetchTriggerTypes() {
    if (!agentId()) return
    const currentScope = scope
    const request = ++typesRequest
    const isCurrent = () =>
      scopeIsCurrent(currentScope) && request === typesRequest
    try {
      const { data } = await service.listTypes(agentId())
      if (!isCurrent()) return
      triggerTypes.value = Object.fromEntries(
        data.map(({ type, ...options }) => [type, options])
      )
      typesLoadError.value = false
    } catch {
      if (!isCurrent()) return
      triggerTypes.value = {}
      typesLoadError.value = true
    } finally {
      if (isCurrent()) typesVersion.value++
    }
  }

  /** Loads again the triggers or the trigger types that failed to load. */
  function retryLoad() {
    if (loadError.value) fetchTriggers()
    if (typesLoadError.value) fetchTriggerTypes()
  }

  /**
   * Creates a trigger of the given type with the type's defaults and the default
   * opening message; the server picks its default overlap rule.
   *
   * @param {string} type The service type of the trigger.
   * @returns {Promise<object|null>} The created trigger, or null when it failed.
   */
  async function createTrigger(type) {
    const currentScope = scope
    const values = newTriggerValues($registry, t, type)
    try {
      const { data } = await service.create(agentId(), values)
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
   *   service values compared field by field, or all of them for a new type.
   */
  function unsavedValues(trigger) {
    const { values } = saved.get(trigger.id)
    const unsaved = Object.fromEntries(
      TRIGGER_FIELDS.filter(
        (field) => !isEqual(trigger[field], values[field])
      ).map((field) => [field, trigger[field]])
    )
    const savedService = 'type' in unsaved ? {} : values.service
    const serviceValues = Object.fromEntries(
      Object.entries(trigger.service).filter(
        ([field, value]) => !isEqual(value, savedService[field])
      )
    )
    if ('type' in unsaved || Object.keys(serviceValues).length) {
      unsaved.service = { type: trigger.service.type, ...serviceValues }
    }
    return unsaved
  }

  /**
   * Sends a trigger's due fields that the server doesn't hold, each alone but a
   * new type with its service and message, unless a save of it is already in
   * flight: that one sends them once it ends.
   *
   * @param {object} trigger The trigger to save.
   */
  async function saveDueFields(trigger) {
    if (inFlight.has(trigger.id)) return
    const currentScope = scope
    inFlight.add(trigger.id)
    savingIds.add(trigger.id)
    try {
      while (scopeIsCurrent(currentScope)) {
        const field = takeDueField(trigger.id)
        if (!field) break
        const unsaved = unsavedValues(trigger)
        const sent = Object.fromEntries(
          (field === 'type' ? TYPE_CHANGE_FIELDS : [field])
            .filter((name) => name in unsaved)
            .map((name) => [name, unsaved[name]])
        )
        if (Object.keys(sent).length) {
          await sendValues(trigger, sent, currentScope)
        }
      }
    } finally {
      inFlight.delete(trigger.id)
      savingIds.delete(trigger.id)
    }
  }

  /**
   * @param {object} trigger The trigger to save.
   * @param {object} sent The values to send.
   * @param {number} currentScope The scope the save started in.
   */
  async function sendValues(trigger, sent, currentScope) {
    try {
      const { data } = await service.update(
        saved.get(trigger.id).agentId,
        trigger.id,
        sent
      )
      if (!scopeIsCurrent(currentScope)) return
      const switchedOnAgain =
        sent.enabled && refusedSwitchOns.delete(trigger.id)
      if ((sent.service && trigger.type === data.type) || switchedOnAgain) {
        delete serviceErrors[trigger.id]
      }
      adoptSaved(trigger, sent, data)
    } catch (error) {
      if (scopeIsCurrent(currentScope)) handleSaveError(trigger, sent, error)
    }
  }

  /**
   * Takes the server's reply as saved, and shows its values where the card still
   * shows what was sent: a field edited meanwhile keeps the newer edit. Service
   * values only merge while the card still shows the response's type. Adopting a
   * different type replaces its service rather than mixing the types' settings.
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
    if (trigger.type === latest.type && trigger.service.type !== latest.type) {
      trigger.service = cloneDeep(latest.service)
      delete serviceErrors[trigger.id]
    } else if (trigger.type === latest.type) {
      const sentService = sent.service || {}
      const previousService = 'type' in sent ? {} : previous.service
      trigger.service = Object.fromEntries(
        Object.entries({ ...trigger.service, ...latest.service }).map(
          ([field, value]) => {
            const showsSaved =
              !(field in trigger.service) ||
              isEqual(
                trigger.service[field],
                field in sentService
                  ? sentService[field]
                  : previousService[field]
              )
            return [field, showsSaved ? value : trigger.service[field]]
          }
        )
      )
    }
    trigger.last_skipped_on = data.last_skipped_on
    trigger.last_skipped_reason = data.last_skipped_reason
    entry.values = latest
  }

  /**
   * Keeps rejected same-type service edits shown with their error, and turns a
   * switch-on the run identity can't back off, with its error. A rejection of
   * service values whose type the card no longer shows leaves no error. A
   * failed type change restores the saved type and service together, unless
   * another type was picked meanwhile. Other failures revert only the values
   * still shown.
   *
   * @param {object} trigger The trigger whose save failed.
   * @param {object} sent The values that were sent.
   * @param {Error} error The failure.
   */
  function handleSaveError(trigger, sent, error) {
    const code = errorCode(error)
    const { values } = saved.get(trigger.id) || {}
    const showsSentService = sent.service?.type === trigger.type
    if (code === API_ERROR_CODE.TRIGGER_SERVICE_MISCONFIGURED) {
      if (!showsSentService) return
      const detail = error.response.data.detail
      serviceErrors[trigger.id] =
        typeof detail === 'string' ? detail : t('agent.triggerMisconfigured')
      if (!('type' in sent)) return
    } else if (code === API_ERROR_CODE.AGENT_TRIGGER_NO_ACCESS) {
      if (sent.service && !showsSentService) return
      serviceErrors[trigger.id] = t('agent.triggerNoAccess')
      if (values && 'enabled' in sent && trigger.enabled === sent.enabled) {
        trigger.enabled = values.enabled
        refusedSwitchOns.add(trigger.id)
      }
      return
    } else if (code === API_ERROR_CODE.AGENT_TRIGGER_DOES_NOT_EXIST) {
      removeTrigger(trigger)
      return
    } else {
      notifyIf(error, 'trigger')
    }
    if (!values) return
    for (const field of TRIGGER_FIELDS) {
      if (field in sent && isEqual(trigger[field], sent[field])) {
        trigger[field] = values[field]
      }
    }
    if (!showsSentService) return
    if ('type' in sent) {
      trigger.service = cloneDeep(values.service)
    } else {
      const reverted = { ...trigger.service }
      for (const [field, value] of Object.entries(sent.service)) {
        if (isEqual(trigger.service[field], value)) {
          reverted[field] = values.service[field]
        }
      }
      trigger.service = reverted
    }
    serviceReverts[trigger.id] = (serviceReverts[trigger.id] || 0) + 1
  }

  function scheduleSave(trigger, fields) {
    addFields(typedFields, trigger.id, fields)
    if (!scheduledSaves.has(trigger.id)) {
      scheduledSaves.set(
        trigger.id,
        debounce(() => {
          addFields(dueFields, trigger.id, typedFields.get(trigger.id) || [])
          typedFields.delete(trigger.id)
          saveDueFields(trigger)
        }, TYPED_SAVE_DELAY)
      )
    }
    scheduledSaves.get(trigger.id)()
  }

  /**
   * Shows a card's edit at once and saves each edited field: a name, a switch or
   * an overlap rule right away, a new type right away with its service and
   * message, a message or service values once typing pauses.
   *
   * @param {object} trigger The trigger the card shows.
   * @param {object} values The edited `type`, `name`, `enabled`, `on_overlap`,
   *   `batch_size`, `message` or service values; a new type comes with all the
   *   values of its service.
   */
  function updateTrigger(trigger, values) {
    if (!saved.has(trigger.id)) return
    for (const field of TRIGGER_FIELDS) {
      if (field in values) trigger[field] = values[field]
    }
    if (values.service) {
      trigger.service =
        'type' in values
          ? values.service
          : { ...trigger.service, ...values.service }
    }
    const edited =
      'type' in values
        ? ['type']
        : SAVED_FIELDS.filter((field) => field in values)
    const picked = edited.filter((field) => PICKED_FIELDS.includes(field))
    const typed = edited.filter((field) => !PICKED_FIELDS.includes(field))
    if (typed.length) scheduleSave(trigger, typed)
    if (picked.length) {
      addFields(dueFields, trigger.id, picked)
      saveDueFields(trigger)
    }
  }

  /**
   * Gives a trigger another type, with that type's default service values. Its
   * message becomes the new type's default only while it is the old type's
   * default, so a message of its own is kept.
   *
   * @param {object} trigger The trigger the card shows.
   * @param {string} type The service type the trigger gets.
   */
  function changeTriggerType(trigger, type) {
    if (type === trigger.type) return
    const serviceType = $registry.get('service', type)
    const values = {
      type,
      service: { type, ...serviceType.getDefaultValues(null, {}) },
    }
    const previousType = serviceTypeOf($registry, trigger.type)
    if (
      previousType &&
      trigger.message?.formula ===
        newTriggerMessage($registry, t, previousType).formula
    ) {
      values.message = newTriggerMessage($registry, t, serviceType)
    }
    updateTrigger(trigger, values)
  }

  /**
   * Removes the trigger at once and trashes it; it comes back if that fails,
   * unless it was already gone.
   *
   * @param {object} trigger The trigger to delete.
   */
  async function deleteTrigger(trigger) {
    const entry = saved.get(trigger.id)
    if (!entry || deletingIds.has(trigger.id)) return
    deletingIds.add(trigger.id)
    scheduledSaves.get(trigger.id)?.cancel()
    try {
      await service.delete(entry.agentId, trigger.id)
      if (saved.get(trigger.id) === entry) removeTrigger(trigger)
    } catch (error) {
      if (saved.get(trigger.id) !== entry) return
      if (errorCode(error) === API_ERROR_CODE.AGENT_TRIGGER_DOES_NOT_EXIST) {
        removeTrigger(trigger)
      } else {
        notifyIf(error, 'trigger')
        if (typedFields.has(trigger.id)) scheduledSaves.get(trigger.id)()
      }
    } finally {
      deletingIds.delete(trigger.id)
    }
  }

  function flushScheduledSaves() {
    for (const scheduled of scheduledSaves.values()) scheduled.flush()
  }

  function reset() {
    flushScheduledSaves()
    for (const triggerId of [...saved.keys()]) forget(triggerId)
    ++scope
    triggers.value = []
    triggerTypes.value = null
    typesLoadError.value = false
    loading.value = false
    loadError.value = false
    savingIds.clear()
    inFlight.clear()
    typedFields.clear()
    dueFields.clear()
  }

  onMounted(() => {
    fetchTriggers()
    fetchTriggerTypes()
  })
  watch(
    () => agent.value?.id,
    () => {
      reset()
      fetchTriggers()
      fetchTriggerTypes()
    }
  )
  watch(() => {
    const runAs = getRunAs()
    return [runAs?.type, runAs?.id, getRunAsStatus(runAs)].join(':')
  }, fetchTriggerTypes)
  onBeforeUnmount(flushScheduledSaves)

  return {
    triggers: computed(() =>
      triggers.value.filter(({ id }) => !deletingIds.has(id))
    ),
    allTriggers: triggers,
    triggerTypes,
    typesVersion,
    loading,
    loadError,
    typesLoadError,
    savingIds,
    serviceErrors,
    serviceReverts,
    retryLoad,
    createTrigger,
    updateTrigger,
    changeTriggerType,
    deleteTrigger,
  }
}
