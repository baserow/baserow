<template>
  <Modal ref="modal" :full-screen="true" :close-button="false">
    <div v-if="loading" class="loading-absolute-center"></div>
    <template v-else>
      <TemplateHeader
        :workspace="workspace"
        :template="selectedTemplate"
        :category="selectedTemplateCategory"
        @installed="hide()"
      ></TemplateHeader>
      <TemplateCategories
        ref="categories"
        :categories="categories"
        :selected-template="selectedTemplate"
        @selected="selectTemplate"
      >
        <div class="modal__actions">
          <a class="modal__close" @click="hide()">
            <i class="iconoir-cancel"></i>
          </a>
        </div>
      </TemplateCategories>
      <TemplatePreview
        :template="selectedTemplate"
        class="templates__body"
      ></TemplatePreview>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'

import TemplateHeader from '@baserow/modules/core/components/template/TemplateHeader'
import TemplateCategories from '@baserow/modules/core/components/template/TemplateCategories'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'

export default {
  name: 'TemplateModal',
  components: { TemplateHeader, TemplateCategories, TemplatePreview },
  mixins: [modal],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: true,
      categories: [],
      selectedTemplate: null,
      selectedTemplateCategory: null,
    }
  },
  methods: {
    /**
     * When the modal is opened we want to fetch all the templates and their
     * categories. They will be placed in the sidebar so that the user can select a
     * template to preview.
     */
    async show(templateId = null, ...args) {
      modal.methods.show.call(this, ...args)

      this.loading = true
      this.categories = []
      this.selectedTemplate = null
      this.selectedTemplateCategory = null

      try {
        const { data } = await TemplateService(this.$client).fetchAll()
        this.categories = data
        this.loading = false
      } catch (error) {
        notifyIf(error, 'templates')
        this.hide()
      }

      // If a template ID is provided when opening, then open that one, otherwise, open
      // the default.
      for (let i = 0; i < this.categories.length; i++) {
        const category = this.categories[i]
        for (let i2 = 0; i2 < category.templates.length; i2++) {
          const template = category.templates[i2]
          if (
            (templateId === null && template.is_default) ||
            (templateId !== null &&
              (template.id === templateId || template.slug === templateId))
          ) {
            this.$nextTick(() => {
              this.$refs.categories.selectCategory(category.id)
              this.selectTemplate({ template, category })
            })
            return
          }
        }
      }
    },
    selectTemplate({ template, category }) {
      this.selectedTemplate = template
      this.selectedTemplateCategory = category
    },
  },
}
</script>
