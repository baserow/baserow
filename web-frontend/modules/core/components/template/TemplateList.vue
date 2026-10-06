<template>
  <div ref="root" class="template-list">
    <div class="template-list__head">
      <div class="template-list__title">
        {{ $t('templateCategories.title') }}
      </div>
    </div>
    <div class="template-list__body">
      <div class="template-list__sidebar">
        <div class="template-list__search">
          <FormInput
            ref="searchInput"
            v-model="search"
            icon-left="iconoir-search"
            :placeholder="$t('templateCategories.search')"
          ></FormInput>
        </div>
        <ul class="template-list__categories">
          <li>
            <a
              class="template-list__category-link"
              :class="{
                'template-list__category-link--active':
                  selectedCategoryId === null,
              }"
              @click="selectedCategoryId = null"
              >{{ $t('templateCategories.allTemplates') }}</a
            >
          </li>
          <li v-for="category in categories" :key="category.id">
            <a
              class="template-list__category-link"
              :class="{
                'template-list__category-link--active':
                  selectedCategoryId === category.id,
              }"
              @click="selectedCategoryId = category.id"
              >{{ category.name }}</a
            >
          </li>
        </ul>
      </div>
      <div class="template-list__content">
        <div
          v-for="category in visibleCategories"
          :key="category.id"
          class="template-list__section"
        >
          <a
            class="template-list__section-title"
            @click="toggleCollapsed(category.id)"
          >
            <i
              :class="
                collapsed.includes(category.id)
                  ? 'iconoir-nav-arrow-right'
                  : 'iconoir-nav-arrow-down'
              "
            ></i>
            {{ category.name }}
          </a>
          <div
            v-if="!collapsed.includes(category.id)"
            class="template-list__grid"
          >
            <a
              v-for="template in category.templates"
              :key="template.id"
              class="template-list__card"
              @click="emit('selected', template)"
            >
              <div class="template-list__card-title">
                <div class="template-list__card-icon">
                  <i :class="template.icon || 'iconoir-view-grid'"></i>
                </div>
                <div class="template-list__card-name">{{ template.name }}</div>
              </div>
              <div
                v-if="template.description"
                class="template-list__card-description"
              >
                {{ template.description }}
              </div>
            </a>
          </div>
        </div>
        <div v-if="visibleCategories.length === 0" class="template-list__empty">
          {{ $t('templateCategories.noResults') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useNuxtApp } from '#app'

import { escapeRegExp } from '@baserow/modules/core/utils/string'

const props = defineProps({
  categories: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['selected'])

const { $priorityBus } = useNuxtApp()

const root = ref(null)
const searchInput = ref(null)
const search = ref('')
const selectedCategoryId = ref(null)
const collapsed = ref([])

function matchesSearch(template, regex) {
  return [template.name, ...template.keywords.split(',')].some((value) =>
    regex.test(value)
  )
}

/**
 * The selected category, or every category, with only the templates that match
 * the search query. Categories without matching templates are left out.
 */
const visibleCategories = computed(() => {
  const categories = props.categories.filter(
    (category) =>
      selectedCategoryId.value === null ||
      category.id === selectedCategoryId.value
  )

  if (search.value === '') {
    return categories
  }

  const regex = new RegExp(escapeRegExp(search.value), 'i')
  return categories
    .map((category) => ({
      ...category,
      templates: category.templates.filter((template) =>
        matchesSearch(template, regex)
      ),
    }))
    .filter((category) => category.templates.length > 0)
})

function toggleCollapsed(categoryId) {
  const index = collapsed.value.indexOf(categoryId)
  if (index === -1) {
    collapsed.value.push(categoryId)
  } else {
    collapsed.value.splice(index, 1)
  }
}

function searchStarted({ event }) {
  // The list stays mounted, but hidden, while a template is previewed.
  if (root.value?.offsetParent === null) {
    return
  }
  event.preventDefault()
  searchInput.value.focus()
}

onMounted(() => {
  $priorityBus.$on('start-search', $priorityBus.level.HIGH, searchStarted)
})

onBeforeUnmount(() => {
  $priorityBus.$off('start-search', searchStarted)
})
</script>
