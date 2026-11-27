<template>
  <Avatar
    :image="integrationType.image || ''"
    :icon="integrationType.iconClass || ''"
    color="transparent"
    :size="size"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'
import Avatar from '@baserow/modules/core/components/Avatar'

const props = defineProps({
  subject: { type: Object, required: true },
  size: { type: String, default: 'large' },
})

const { $registry } = useNuxtApp()

const integrationType = computed(() =>
  $registry.get('integration', props.subject.type)
)
</script>
