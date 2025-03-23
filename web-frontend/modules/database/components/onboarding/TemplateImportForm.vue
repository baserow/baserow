<template>
  <div>
    <div v-if="loading" class="loading"></div>
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
import { clone } from '@baserow/modules/core/utils/object'
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
      const allTemplates = []
      this.categories.forEach((category) => {
        category.templates.forEach((template) => {
          allTemplates.push(template)
        })
      })

      return allTemplates.slice(0, 6)

      // if (this.search === '') {
      //   return this.categories
      // }
      //
      // return clone(this.categories)
      //   .map((category) => {
      //     category.templates = category.templates.filter((template) => {
      //       const keywords = template.keywords.split(',')
      //       keywords.push(template.name)
      //       const regex = new RegExp('(' + escapeRegExp(this.search) + ')', 'i')
      //       return keywords.some((value) => value.match(regex))
      //     })
      //     return category
      //   })
      //   .filter((category) => category.templates.length > 0)
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
