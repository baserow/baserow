<template>
  <ViewsAdminTable></ViewsAdminTable>
</template>

<script setup>
import { useHead, useNuxtApp } from '#imports'
import ViewsAdminTable from '@baserow/modules/database/components/admin/views/ViewsAdminTable'

definePageMeta({
  layout: 'app',
  middleware: ['staff', 'databaseDomain'],
})

const { $i18n } = useNuxtApp()
useHead({ title: $i18n.t('viewsAdmin.title') })
</script>
