<template>
  <Modal
    ref="modal"
    class="templates-modal"
    :full-screen="true"
    :close-button="false"
    keep-content
  >
    <div v-if="loading" class="loading-absolute-center"></div>
    <template v-else>
      <TemplateDetails
        v-if="selectedTemplate !== null"
        :key="selectedTemplate.id"
        :template="selectedTemplate"
        :categories="selectedTemplateCategories"
        :workspace="workspace"
        show-back
        class="templates__body"
        @back="selectedTemplate = null"
        @installed="hide()"
      ></TemplateDetails>
      <TemplateList
        v-show="selectedTemplate === null"
        :categories="categories"
        class="templates__body"
        @selected="selectTemplate"
      ></TemplateList>
      <div class="modal__actions">
        <a class="modal__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'

import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import TemplateList from '@baserow/modules/core/components/template/TemplateList'

export default {
  name: 'TemplateModal',
  components: { TemplateDetails, TemplateList },
  mixins: [modal],
  props: {
    // When no workspace is provided, the user must choose the workspace to install
    // the template into.
    workspace: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      loading: true,
      categories: [],
      selectedTemplate: null,
    }
  },
  computed: {
    selectedTemplateCategories() {
      return this.categories.filter((category) =>
        category.templates.some((t) => t.id === this.selectedTemplate.id)
      )
    },
  },
  methods: {
    /**
     * When the modal is opened we want to fetch all the templates and their
     * categories, so that the user can browse them. If a template id or slug is
     * provided, the details of that template are opened right away.
     */
    async show(templateId = null, ...args) {
      modal.methods.show.call(this, ...args)

      this.loading = true
      this.categories = []
      this.selectedTemplate = null

      try {
        const { data } = await TemplateService(this.$client).fetchAll()
        this.categories = data
        this.loading = false
      } catch (error) {
        notifyIf(error, 'templates')
        this.hide()
        return
      }

      if (templateId !== null) {
        const template = this.categories
          .flatMap((category) => category.templates)
          .find((t) => t.id === templateId || t.slug === templateId)
        if (template) {
          this.selectTemplate(template)
        }
      }
    },
    selectTemplate(template) {
      this.selectedTemplate = template
    },
    async hide(...args) {
      modal.methods.hide.call(this, ...args)
      this.selectedTemplate = null
    },
  },
}
</script>
