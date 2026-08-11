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
      <div
        class="template-import-items"
        :class="{ 'template-import-items--wide': wide }"
      >
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
import uniqBy from 'lodash/uniqBy'
import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { escapeRegExp } from '@baserow/modules/core/utils/string'

export default {
  name: 'TemplateImportForm',
  props: {
    // Can be provided if the templates have already been fetched, to avoid fetching
    // them a second time.
    providedCategories: {
      type: Array,
      required: false,
      default: null,
    },
    // Additionally moves the default template to the front, so that it's always
    // visible when it's selected.
    autoSelectDefault: {
      type: Boolean,
      required: false,
      default: false,
    },
    limit: {
      type: Number,
      required: false,
      default: 6,
    },
    wide: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['selected-template'],
  data() {
    return {
      loading: true,
      categories: [],
      search: '',
      selectedTemplate: 0,
    }
  },
  computed: {
    databaseTemplates() {
      // Categories can contain the same templates, so they must be deduplicated. If
      // `open_application == null`, then it falls back on the normal behavior, which
      // is opening the first database. An `open_application` is typically set if an
      // application must be opened first, and the onboarding experience works best by
      // starting with a database, so we're filtering those out.
      const templates = this.categories.flatMap(
        (category) => category.templates
      )
      return uniqBy(templates, 'id').filter(
        (template) => template.open_application === null
      )
    },
    templates() {
      if (this.search) {
        return this.matchingTemplates(this.search).slice(0, this.limit)
      }

      // A few selected templates have the keyword `onboarding`. Those are the ones
      // that are suggested if the user isn't searching.
      const suggested = this.matchingTemplates('onboarding')
      // The default template doesn't necessarily have the `onboarding` keyword, so it's
      // added first to make sure the automatically selected one is visible.
      const defaultTemplates = this.autoSelectDefault
        ? this.databaseTemplates.filter((template) => template.is_default)
        : []

      return uniqBy(
        [
          ...defaultTemplates,
          ...suggested,
          ...this.sameCategoryTemplates(suggested),
        ],
        'id'
      ).slice(0, this.limit)
    },
  },
  async mounted() {
    if (this.providedCategories !== null) {
      this.categories = this.providedCategories
    } else {
      try {
        const { data } = await TemplateService(this.$client).fetchAll()
        this.categories = data
      } catch (error) {
        notifyIf(error, 'templates')
      }
    }
    this.loading = false

    if (this.autoSelectDefault && this.templates.length > 0) {
      this.selectTemplate(this.templates[0])
    }
  },
  methods: {
    matchingTemplates(search) {
      const regex = new RegExp('(' + escapeRegExp(search) + ')', 'i')
      return this.databaseTemplates.filter((template) =>
        [...template.keywords.split(','), template.name].some((value) =>
          value.match(regex)
        )
      )
    },
    /**
     * There can be fewer suggestions than can be shown. The remaining spots are filled
     * up with the templates of the categories the suggestions are in, because the other
     * categories can contain templates that only demonstrate a specific feature.
     */
    sameCategoryTemplates(templates) {
      const ids = new Set(templates.map((template) => template.id))
      const relatedIds = new Set(
        this.categories
          .filter((category) =>
            category.templates.some((template) => ids.has(template.id))
          )
          .flatMap((category) => category.templates)
          .map((template) => template.id)
      )
      return this.databaseTemplates.filter((template) =>
        relatedIds.has(template.id)
      )
    },
    selectTemplate(template) {
      this.selectedTemplate = template.id
      this.$emit('selected-template', template)
    },
  },
}
</script>
