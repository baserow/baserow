import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import debounce from 'lodash/debounce'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * A locally editable copy of a text field of the agent definition that is
 * auto-saved with a debounce. A remote agent update (e.g. the agent
 * rewriting its own memory) only re-seeds the field when the user hasn't
 * diverged from the last seeded value, so an active edit is never stomped.
 */
export function useSeededAgentField(field, { canUpdate }) {
  const store = useStore()
  const agent = computed(() => store.getters['agentApplication/getAgent'])

  const value = ref(agent.value?.[field] || '')
  let seeded = agent.value?.[field] || ''

  // Deep watch, because agent updates mutate the same store object.
  watch(
    agent,
    (newAgent) => {
      const newValue = newAgent?.[field] || ''
      if (value.value === seeded) {
        value.value = newValue
      }
      seeded = newValue
    },
    { deep: true }
  )

  const save = async () => {
    if (!agent.value || !canUpdate.value) {
      return
    }
    // Never PATCH a value that already matches the agent, otherwise the
    // realtime echo of our own save could re-trigger the cycle.
    if (value.value === (agent.value[field] || '')) {
      return
    }
    try {
      await store.dispatch('agentApplication/update', {
        agentId: agent.value.id,
        values: { [field]: value.value },
      })
    } catch (error) {
      notifyIf(error, 'application')
    }
  }
  const debouncedSave = debounce(save, 1000)
  const onInput = () => debouncedSave()
  const setValue = (newValue) => {
    value.value = newValue
    debouncedSave()
  }

  onBeforeUnmount(() => debouncedSave.flush())

  return { agent, value, onInput, setValue, flush: () => debouncedSave.flush() }
}
