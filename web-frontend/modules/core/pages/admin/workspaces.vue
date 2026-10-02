<template>
  <WorkspacesAdminTable></WorkspacesAdminTable>
</template>

<script setup>
import { useHead, useNuxtApp } from '#imports'
import WorkspacesAdminTable from '@baserow/modules/core/components/admin/workspaces/WorkspacesAdminTable'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const { $i18n } = useNuxtApp()
useHead({ title: $i18n.t('adminWorkspaces.title') })
</script>
