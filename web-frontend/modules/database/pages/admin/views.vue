<template>
  <ViewsAdminTable></ViewsAdminTable>
</template>

<script setup>
import { useHead, useNuxtApp } from '#imports'
import ViewsAdminTable from '@baserow/modules/database/components/admin/views/ViewsAdminTable'

// Page metadata overrides route metadata, so the database guard must stay here
// alongside the staff guard to load view types before the admin table renders.
definePageMeta({
  layout: 'app',
  middleware: ['staff', 'databaseDomain'],
})

const { $i18n } = useNuxtApp()
useHead({ title: $i18n.t('viewsAdmin.title') })
</script>
