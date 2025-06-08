<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :data-providers="dataProviders"
    :application-context="applicationContext"
    v-on="$listeners"
  />
</template>

<script setup>
import { inject, computed, useContext } from '@nuxtjs/composition-api'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'

const props = defineProps({
  dataProvidersAllowed: { type: Array, required: false, default: () => [] },
})

const applicationContext = inject('applicationContext')

const { app } = useContext()
const dataProviders = computed(() => {
  return props.dataProvidersAllowed.map((dataProviderName) =>
    app.$registry.get('automationDataProvider', dataProviderName)
  )
})
</script>
