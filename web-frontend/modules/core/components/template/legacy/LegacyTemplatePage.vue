<template>
  <TemplatePage v-if="template.type === 'user'" />
  <TemplatePreview v-else :template="template" />
</template>

<script setup>
import TemplatePage from '@baserow/modules/core/components/template/TemplatePage'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

const route = useRoute()
const { $client } = useNuxtApp()

const slug = route.params.slug

const { data: template, error } = await useAsyncData(
  `legacy-template-${slug}`,
  async () => {
    try {
      const { data } = await TemplateService($client).fetch(slug)
      return data
    } catch (e) {
      if (e.response?.status === 404) {
        throw createError({
          statusCode: 404,
          message: 'Template not found.',
          data: { report: false },
          fatal: true,
        })
      }
      throw e
    }
  }
)

if (error.value) {
  throw error.value
}
</script>
