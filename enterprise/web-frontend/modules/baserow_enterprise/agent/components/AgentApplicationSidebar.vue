<template>
  <SidebarApplication
    :workspace="workspace"
    :application="application"
    :highlighted="selected"
    @selected="selectApplication"
  />
</template>

<script setup>
import { computed } from 'vue'
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  application: { type: Object, required: true },
  workspace: { type: Object, required: true },
})
const { $store, $registry } = useNuxtApp()
const selected = computed(() =>
  $store.getters['application/isSelected'](props.application)
)

async function selectApplication() {
  try {
    await $registry.get('application', 'agent').select(props.application)
  } catch (error) {
    notifyIf(error, 'application')
  }
}
</script>
