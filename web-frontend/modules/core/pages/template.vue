<template>
  <div v-if="!ready" class="skeleton">
    <div
      class="skeleton__item skeleton__item--heading skeleton__item--w-md"
    ></div>
    <div class="skeleton__item skeleton__item--block"></div>
  </div>
  <TemplatePreview v-else-if="template" :template="template" />
  <div v-else>error</div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useNuxtApp } from '#app'

import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

const route = useRoute()
const { $client } = useNuxtApp()

const { data, ready } = await usePageAsyncData(
  `template-${route.params.slug}`,
  async () => {
    try {
      const { data } = await TemplateService($client).fetch(route.params.slug)
      return { template: data }
    } catch {
      // A bad slug must show the inline error fallback below instead of the
      // Nuxt error page, so the error is swallowed on purpose.
      return { template: null }
    }
  }
)

const template = computed(() => data.value?.template ?? null)
</script>
