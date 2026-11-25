import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { API_ERROR_CODE } from '@baserow/modules/agent/constants'
import AgentChannelService from '@baserow_enterprise/services/agentChannels'

export const PUBLIC_CHAT_CHANNEL_TYPE = 'public_chat'

/**
 * The channels of one Agent. Changes show at once, and a failed save puts the
 * saved values back where the channel still shows what was sent. A password
 * shows only once saved.
 *
 * @param {import('vue').Ref<object>} agent The Agent whose channels are listed.
 * @param {object} options
 * @param {boolean} options.load False for a template preview, which never carries channels.
 * @returns {object} The channels, their loading and saving state, and actions.
 */
export function useAgentChannels(agent, { load = true } = {}) {
  const { $client } = useNuxtApp()
  const service = AgentChannelService($client)
  const allChannels = ref([])
  const loading = ref(false)
  const loadError = ref(false)
  const savingIds = reactive(new Set())
  const deletingIds = reactive(new Set())
  const savesInFlight = new Map()
  const saved = new Map()
  let listRequest = 0

  const track = (channel) => saved.set(channel.id, { ...channel })

  function remove(channel) {
    saved.delete(channel.id)
    allChannels.value = allChannels.value.filter(({ id }) => id !== channel.id)
  }

  async function fetchChannels() {
    const agentId = agent.value?.id
    if (!agentId || !load) return
    const request = ++listRequest
    const isCurrent = () => request === listRequest
    loading.value = true
    loadError.value = false
    try {
      const { data } = await service.list(agentId)
      if (!isCurrent()) return
      data.forEach(track)
      allChannels.value = data
    } catch {
      if (isCurrent()) loadError.value = true
    } finally {
      if (isCurrent()) loading.value = false
    }
  }

  /** @returns {Promise<object|null>} The new public chat, or null when it failed. */
  async function createChannel() {
    const agentId = agent.value.id
    try {
      const { data } = await service.create(agentId, {
        type: PUBLIC_CHAT_CHANNEL_TYPE,
      })
      if (agent.value?.id === agentId) {
        track(data)
        allChannels.value.push(data)
      }
      return data
    } catch (error) {
      notifyIf(error, 'channel')
      return null
    }
  }

  /**
   * Runs the save after the channel's previous one, so two never race.
   *
   * @param {object} channel The channel the save changes.
   * @param {Function} send Sends the change.
   * @returns {Promise} Settles as `send` does.
   */
  async function queueSave(channel, send) {
    savingIds.add(channel.id)
    const save = (savesInFlight.get(channel.id) || Promise.resolve()).then(send)
    const settled = save.catch(() => {})
    savesInFlight.set(channel.id, settled)
    try {
      return await save
    } finally {
      if (savesInFlight.get(channel.id) === settled) {
        savesInFlight.delete(channel.id)
        savingIds.delete(channel.id)
      }
    }
  }

  /**
   * @param {object} channel The channel as its card shows it.
   * @param {object} values Any of `enabled`, `title` and `welcome_text`.
   */
  async function updateChannel(channel, values) {
    const agentId = agent.value.id
    const stillShown = () =>
      Object.keys(values).filter((field) => channel[field] === values[field])
    Object.assign(channel, values)
    await queueSave(channel, async () => {
      try {
        const { data } = await service.update(agentId, channel.id, values)
        for (const field of stillShown()) channel[field] = data[field]
        if (saved.has(channel.id)) track(data)
      } catch (error) {
        const savedValues = saved.get(channel.id)
        if (savedValues) {
          for (const field of stillShown()) channel[field] = savedValues[field]
        }
        notifyIf(error, 'channel')
      }
    })
  }

  /**
   * Waits for the server, because a link that looks protected before it is
   * could be shared on that belief.
   *
   * @param {object} channel The channel as its card shows it.
   * @param {string} password The new password, or '' to remove it.
   * @throws The request's error, for the caller to show.
   */
  async function savePassword(channel, password) {
    const agentId = agent.value.id
    await queueSave(channel, async () => {
      const { data } = await service.update(agentId, channel.id, { password })
      channel.has_password = data.has_password
      if (saved.has(channel.id)) track(data)
    })
  }

  /** Hides the channel at once and trashes it; it comes back if that fails. */
  async function deleteChannel(channel) {
    if (deletingIds.has(channel.id)) return
    deletingIds.add(channel.id)
    try {
      await service.delete(agent.value.id, channel.id)
      remove(channel)
    } catch (error) {
      if (
        error.response?.data?.error ===
        API_ERROR_CODE.AGENT_CHANNEL_DOES_NOT_EXIST
      ) {
        remove(channel)
      } else {
        notifyIf(error, 'channel')
      }
    } finally {
      deletingIds.delete(channel.id)
    }
  }

  onMounted(fetchChannels)
  watch(
    () => agent.value?.id,
    () => {
      saved.clear()
      allChannels.value = []
      fetchChannels()
    }
  )

  return {
    channels: computed(() =>
      allChannels.value.filter(({ id }) => !deletingIds.has(id))
    ),
    loading,
    loadError,
    savingIds,
    retryLoad: fetchChannels,
    createChannel,
    updateChannel,
    savePassword,
    deleteChannel,
  }
}
