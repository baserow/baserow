<template>
  <TemplatesAdminTable v-if="$featureFlagIsEnabled(FF_USER_TEMPLATES)" />
</template>

<script setup>
import { useHead } from '#imports'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplatesAdminTable from '@baserow/modules/core/components/admin/templates/TemplatesAdminTable'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

const { $i18n } = useNuxtApp()
useHead({ title: $i18n.t('templatesAdmin.title') })
</script>
