<template>
  <Context
    ref="context"
    class="agent-trigger-picker"
    max-height-if-outside-viewport
    @shown="focusMenu"
  >
    <GroupedMenu
      ref="menu"
      :items="groups"
      :search-placeholder="$t('agent.searchTriggerTypes')"
      :empty-text="$t('agent.noTriggerTypes')"
      @select="select"
      @close="context.hide()"
    />
  </Context>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useNuxtApp } from '#app'
import Context from '@baserow/modules/core/components/Context'
import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'

const props = defineProps({
  /** The trigger types the Agent's configuration offers. */
  availableTypes: { type: Array, required: true },
  /** The Agent's workspace, which decides the deactivated types. */
  workspace: { type: Object, default: null },
})
const emit = defineEmits(['select'])
const { $registry } = useNuxtApp()
const context = ref(null)
const menu = ref(null)

const triggerTypes = computed(() =>
  $registry
    .getOrderedList('service')
    .filter(
      (serviceType) =>
        serviceType.isTrigger &&
        props.availableTypes.includes(serviceType.getType())
    )
)
const groups = computed(() => {
  const byGroup = new Map()
  for (const serviceType of triggerTypes.value) {
    const group = serviceType.group
    if (!byGroup.has(group.id))
      byGroup.set(group.id, { ...group, children: [] })
    byGroup.get(group.id).children.push({
      id: serviceType.getType(),
      value: serviceType.getType(),
      label: serviceType.name,
      description: serviceType.description,
      icon: serviceType.icon,
      iconColor: serviceType.iconColor,
      disabled: serviceType.isDeactivated({ workspace: props.workspace }),
      disabledReason: serviceType.isDeactivatedReason({
        workspace: props.workspace,
      }),
    })
  }
  return [...byGroup.values()]
})

async function focusMenu() {
  await nextTick()
  menu.value?.focus()
}

function select(item) {
  context.value.hide()
  emit('select', item.value)
}

/**
 * Opens or closes the picker next to the element that opened it.
 *
 * @param {HTMLElement} target The element the picker is placed against.
 */
function toggle(target) {
  context.value.toggle(target, 'bottom', 'right', 4)
}

defineExpose({ toggle })
</script>
