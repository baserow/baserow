<template>
  <div class="tabs-body">
    <div class="tabs-body__tabs">
      <Tabs
        :route="route"
        offset
        large-offset
        :tab-items="[
          {
            title: $t('dataScanner.scansTab'),
            to: { name: 'admin-data-scanner-scans' },
          },
          {
            title: $t('dataScanner.resultsTab'),
            to: { name: 'admin-data-scanner-results' },
          },
        ]"
      >
      </Tabs>
    </div>
    <div class="tabs-body__body">
      <NuxtPage />
    </div>
  </div>
</template>

<script setup>
import { useStore } from 'vuex'
import { useNuxtApp, createError, definePageMeta, useHead } from '#imports'
import EnterpriseFeatures from '@baserow_enterprise/features'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const route = useRoute()
const store = useStore()
const { $hasFeature, $i18n } = useNuxtApp()

useHead({ title: $i18n.t('dataScanner.title') })

if (!$hasFeature(EnterpriseFeatures.DATA_SCANNER)) {
  throw createError({
    statusCode: 401,
    message: 'Available in the enterprise version',
  })
}

if (!store.getters['auth/isStaff']) {
  throw createError({ statusCode: 403, message: 'Forbidden.' })
}
</script>
