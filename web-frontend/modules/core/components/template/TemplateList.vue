<template>
  <div class="template-list">
    <div
      class="template-list__head"
      :class="{ 'template-list__head--centered': $slots.head }"
    >
      <slot name="head">
        <div class="template-list__title">
          {{ $t('templateCategories.title') }}
        </div>
      </slot>
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
              role="button"
              tabindex="0"
              @click="selectedCategoryId = null"
              @keydown.enter.prevent="selectedCategoryId = null"
              @keydown.space.prevent="selectedCategoryId = null"
              >{{ $t('templateCategories.allTemplates') }}</a
            >
          </li>
          <li v-for="category in sortedCategories" :key="category.id">
            <a
              class="template-list__category-link"
              :class="{
                'template-list__category-link--active':
                  selectedCategoryId === category.id,
              }"
              role="button"
              tabindex="0"
              @click="selectedCategoryId = category.id"
              @keydown.enter.prevent="selectedCategoryId = category.id"
              @keydown.space.prevent="selectedCategoryId = category.id"
              >{{ categoryName(category) }}</a
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
            role="button"
            tabindex="0"
            @click="toggleCollapsed(category.id)"
            @keydown.enter.prevent="toggleCollapsed(category.id)"
            @keydown.space.prevent="toggleCollapsed(category.id)"
          >
            <i
              :class="
                collapsed.includes(category.id)
                  ? 'iconoir-nav-arrow-right'
                  : 'iconoir-nav-arrow-down'
              "
            ></i>
            {{ categoryName(category) }}
          </a>
          <div
            v-if="!collapsed.includes(category.id)"
            class="template-list__grid"
          >
            <a
              v-for="template in category.templates"
              :key="template.id"
              class="template-list__card"
              role="button"
              tabindex="0"
              @click="emit('selected', template)"
              @keydown.enter.prevent="emit('selected', template)"
              @keydown.space.prevent="emit('selected', template)"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'

import { escapeRegExp } from '@baserow/modules/core/utils/string'
import {
  getCategoryName,
  sortCategories,
} from '@baserow/modules/core/utils/templateCategory'

const props = defineProps({
  categories: {
    type: Array,
    required: true,
  },
  // Whether the list is shown. A hidden list must not claim the search shortcut,
  // because only the listener with the highest priority receives it.
  active: {
    type: Boolean,
    required: false,
    default: true,
  },
  initialCategoryId: {
    type: Number,
    required: false,
    default: null,
  },
})

const emit = defineEmits(['selected'])

const { $i18n, $priorityBus } = useNuxtApp()

const searchInput = ref(null)
const search = ref('')
const selectedCategoryId = ref(props.initialCategoryId)
const collapsed = ref([])

const sortedCategories = computed(() => sortCategories(props.categories, $i18n))

function categoryName(category) {
  return getCategoryName(category, $i18n)
}

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
  const categories = sortedCategories.value.filter(
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
  event.preventDefault()
  searchInput.value.focus()
}

function listenToSearch(active) {
  $priorityBus.$off('start-search', searchStarted)
  if (active) {
    $priorityBus.$on('start-search', $priorityBus.level.HIGH, searchStarted)
  }
}

onMounted(() => listenToSearch(props.active))
watch(() => props.active, listenToSearch)

onBeforeUnmount(() => {
  $priorityBus.$off('start-search', searchStarted)
})
</script>
