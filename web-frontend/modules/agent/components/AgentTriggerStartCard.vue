<template>
  <div
    class="agent-trigger-start"
    :class="{ 'agent-trigger-start--expanded': expanded }"
  >
    <button
      type="button"
      class="agent-trigger-start__header"
      :aria-expanded="expanded"
      :aria-controls="textId"
      @click="expanded = !expanded"
    >
      <i class="agent-trigger-start__icon" :class="icon" aria-hidden="true" />
      <span class="agent-trigger-start__title">{{ title }}</span>
      <i
        class="agent-trigger-start__chevron"
        :class="expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'"
        aria-hidden="true"
      />
    </button>
    <div :id="textId" class="agent-trigger-start__text">
      {{ expanded ? content : firstLine }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'

/** The opening message of a trigger-started conversation. */
const props = defineProps({
  /** The resolved trigger message, exactly what the agent received. */
  content: { type: String, required: true },
  /** The trigger's service type key, null once the trigger is permanently deleted. */
  triggerType: { type: String, default: null },
  /** The trigger's current name, blank or null when it has none. */
  triggerName: { type: String, default: null },
})

const { $registry } = useNuxtApp()
const { t } = useI18n()
const textId = useId()
const expanded = ref(false)
const serviceType = computed(() => serviceTypeOf($registry, props.triggerType))
const icon = computed(() => serviceType.value?.icon || 'iconoir-flash')
const title = computed(() => {
  const name = props.triggerName || serviceType.value?.name
  return name ? t('agent.startedBy', { name }) : t('agent.startedByTrigger')
})
const firstLine = computed(() => props.content.trim().split('\n', 1)[0])
</script>
