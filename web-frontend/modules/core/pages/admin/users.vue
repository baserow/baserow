<template>
  <UsersAdminTable></UsersAdminTable>
</template>

<script setup>
import { useHead, useNuxtApp } from '#imports'
import UsersAdminTable from '@baserow/modules/core/components/admin/users/UsersAdminTable'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const { $i18n } = useNuxtApp()
useHead({ title: $i18n.t('adminUsers.title') })
</script>
