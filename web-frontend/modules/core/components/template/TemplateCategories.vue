<template>
  <div class="templates__sidebar">
    <slot></slot>
    <div class="templates__sidebar-title">
      {{ $t('templateCategories.title') }}
    </div>
    <div class="templates__search">
      <FormInput
        ref="searchInput"
        v-model="search"
        icon-left="iconoir-search"
        :placeholder="$t('templateCategories.search')"
      ></FormInput>
    </div>
    <ul class="templates__categories">
      <li
        v-for="category in matchingCategories"
        :key="category.id"
        class="templates__category"
        :class="{
          'templates__category--open': category.id === selectedCategoryId,
        }"
      >
        <a class="templates__category-link" @click="selectCategory(category.id)"
          >{{ category.name }}
          <i
            class="templates__category-link-caret-right iconoir-nav-arrow-right"
          ></i>
          <i
            class="templates__category-link-caret-down iconoir-nav-arrow-down"
          ></i>
        </a>

        <ul class="templates__templates">
          <li
            v-for="template in category.templates"
            :key="template.id"
            class="templates__template"
            :class="{
              'templates__template--active':
                selectedTemplate !== null && template.id == selectedTemplate.id,
            }"
          >
            <a
              class="templates__template-link"
              @click="$emit('selected', { template, category })"
            >
              <i :class="template.icon"></i>
              <span class="templates__template-link-text">{{
                template.name
              }}</span>
            </a>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>

<script>
import templateCategories from '@baserow/modules/core/mixins/templateCategories'

export default {
  name: 'TemplateCategories',
  mixins: [templateCategories],
  props: {
    selectedTemplate: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  emits: ['selected'],
  mounted() {
    this.$priorityBus.$on(
      'start-search',
      this.$priorityBus.level.HIGH,
      this.searchStarted
    )
  },
  beforeUnmount() {
    this.$priorityBus.$off('start-search', this.searchStarted)
  },
  methods: {
    searchStarted({ event }) {
      event.preventDefault()
      this.$refs.searchInput.focus()
    },
  },
}
</script>
