<template>
  <Button
    type="secondary"
    icon="iconoir-refresh-double"
    :loading="refreshing"
    :disabled="refreshing"
    @click="refresh"
    >{{ $t('dashboardFilter.refresh') }}</Button
  >
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'
const props = defineProps({ storePrefix: { type: String, default: '' } })
const { $store } = useNuxtApp()
const refreshing = computed(
  () => $store.getters[`${props.storePrefix}dashboardApplication/isRefreshing`]
)
const refresh = () =>
  $store.dispatch(`${props.storePrefix}dashboardApplication/refresh`)
</script>
