<template>
  <div>
    <div v-if="loading" class="flex justify-content-center">
      <div class="loading"></div>
    </div>
    <div v-else>
      <FormInput
        v-model="search"
        icon-left="iconoir-search"
        :placeholder="$t('templateCategories.search')"
        class="margin-bottom-2"
      ></FormInput>
      <div class="template-import-items">
        <a
          v-for="template in templates"
          :key="template.id"
          class="template-import-item"
          :class="{
            'template-import-item--active': template.id === selectedTemplate,
          }"
          @click="selectTemplate(template)"
        >
          <div class="template-import-item__head">
            <i class="template-import-item__icon" :class="template.icon"></i>
          </div>
          <div class="template-import-item__name">{{ template.name }}</div>
        </a>
      </div>
    </div>
  </div>
</template>

<script>
import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { escapeRegExp } from '@baserow/modules/core/utils/string'

export default {
  name: 'TemplateImportForm',
  data() {
    return {
      loading: true,
      categories: [],
      search: '',
      selectedTemplate: 0,
    }
  },
  computed: {
    templates() {
      let allTemplates = []
      this.categories.forEach((category) => {
        category.templates.forEach((template) => {
          // Categories can have the same templates. We should not have duplicates.
          if (allTemplates.findIndex((t) => t.id === template.id) === -1) {
            allTemplates.push(template)
          }
        })
      })

      // A few selected templates have the keyword `onboarding`. These are shown when
      // no search query is provided.
      const search = this.search || 'onboarding'
      allTemplates = allTemplates
        .filter((template) => {
          // If `open_application == null`, then it falls back on the normal behavior,
          // which is opening the first database. An `open_application` is typically
          // set, if an application must be opened first. The onboarding experience
          // works best by starting with a database, so we're filtering those out.
          return template.open_application === null
        })
        .filter((template) => {
          const keywords = template.keywords.split(',')
          keywords.push(template.name)
          const regex = new RegExp('(' + escapeRegExp(search) + ')', 'i')
          return keywords.some((value) => value.match(regex))
        })

      return allTemplates.slice(0, 6)
    },
  },
  async mounted() {
    try {
      const { data } = await TemplateService(this.$client).fetchAll()
      this.categories = data
    } catch (error) {
      notifyIf(error, 'templates')
    }
    this.loading = false
  },
  methods: {
    selectTemplate(template) {
      this.selectedTemplate = template.id
      this.$emit('selected-template', template)
    },
  },
}
</script>
