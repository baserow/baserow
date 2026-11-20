<template>
  <div class="data-table__text-field" :title="name">{{ name }}</div>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'

const props = defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})

const { $registry } = useNuxtApp()

const name = computed(() => $registry.get('integration', props.row.type).name)
</script>
