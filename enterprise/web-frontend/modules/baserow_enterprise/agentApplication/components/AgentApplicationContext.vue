<template>
  <ApplicationContext
    ref="context"
    :application="application"
    :workspace="workspace"
  />
</template>

<script setup>
import { ref } from 'vue'
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext'

defineProps({
  application: { type: Object, required: true },
  workspace: { type: Object, required: true },
})
// The shared application context sends rename through its containing component.
defineEmits(['rename'])
const context = ref(null)
defineExpose({
  toggle: (...args) => context.value.toggle(...args),
  hide: () => context.value.hide(),
})
</script>
