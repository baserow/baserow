<template>
  <TemplatePreview v-if="template" :template="template" />
  <div v-else>error</div>
</template>

<script>
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

export default {
  name: 'Template',
  components: { TemplatePreview },
  async asyncData({ store, params, error, $client, ...rest }) {
    const slug = params.slug
    try {
      const { data } = await TemplateService($client).fetch(slug)

      return { template: data }
    } catch (error) {
      return { template: null }
    }
  },
}
</script>
