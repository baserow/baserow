<template>
  <!-- The frame and the sidebar are shared with the list of the official
  templates. -->
  <div class="template-list shared-template-list">
    <div
      class="template-list__head"
      :class="{ 'template-list__head--centered': $slots.head }"
    >
      <slot name="head">
        <div class="template-list__title">
          {{ $t('sharedTemplateList.title') }}
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
          <li
            v-for="category in [
              { id: null, name: allTemplates },
              ...categories,
            ]"
            :key="category.id"
          >
            <a
              class="template-list__category-link"
              :class="{
                'template-list__category-link--active':
                  categoryId === category.id,
              }"
              role="button"
              tabindex="0"
              @click="selectCategory(category.id)"
              @keydown.enter.prevent="selectCategory(category.id)"
              @keydown.space.prevent="selectCategory(category.id)"
              >{{ category.name }}</a
            >
          </li>
        </ul>
      </div>
      <div class="shared-template-list__content">
        <div v-if="!loaded" class="shared-template-list__loading">
          <div class="loading"></div>
        </div>
        <TemplateEmptyState
          v-else-if="failed"
          icon="iconoir-warning-triangle"
          :title="$t('sharedTemplateList.errorTitle')"
          :description="$t('sharedTemplateList.errorDescription')"
        >
          <Button type="secondary" :loading="loading" @click="fetchPage()">
            {{ $t('sharedTemplateList.retry') }}
          </Button>
        </TemplateEmptyState>
        <TemplateEmptyState
          v-else-if="templates.length === 0"
          icon="iconoir-group"
          :query="loadedSearch"
          :title="
            categoryId === null
              ? $t('sharedTemplateList.emptyTitle')
              : $t('sharedTemplateList.emptyCategoryTitle')
          "
          :description="$t('sharedTemplateList.emptyDescription')"
        ></TemplateEmptyState>
        <InfiniteScroll
          v-else
          class="shared-template-list__scroll"
          :current-count="templates.length"
          :has-more-page="nextCursor !== null"
          :page-size="PAGE_SIZE"
          :loading="loading"
          :render-end="false"
          @load-next-page="fetchPage(nextCursor)"
        >
          <div class="template-list__grid">
            <a
              v-for="template in templates"
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
              <div class="shared-template-list__card-footer">
                <div
                  v-if="template.author_name"
                  class="shared-template-list__author"
                >
                  <Avatar
                    :initials="template.author_name.charAt(0).toUpperCase()"
                    size="small"
                    rounded
                  ></Avatar>
                  <span class="shared-template-list__author-name">{{
                    isOwnTemplate(template)
                      ? $t('sharedTemplateList.you')
                      : template.author_name
                  }}</span>
                </div>
              </div>
            </a>
          </div>
        </InfiniteScroll>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import debounce from 'lodash/debounce'

import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { isOwnTemplate } from '@baserow/modules/core/utils/userTemplate'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import TemplateEmptyState from '@baserow/modules/core/components/template/TemplateEmptyState'

const PAGE_SIZE = 20

const props = defineProps({
  // Whether the list is shown. A hidden list must not claim the search shortcut,
  // because only the listener with the highest priority receives it.
  active: {
    type: Boolean,
    required: false,
    default: true,
  },
})

const emit = defineEmits(['selected'])

const { $client, $i18n, $priorityBus } = useNuxtApp()

const allTemplates = computed(() => $i18n.t('templateCategories.allTemplates'))

// The categories holding a shared template.
const categories = ref([])
const searchInput = ref(null)
const search = ref('')
const categoryId = ref(null)
const templates = ref([])
// Where the next page continues, null when no templates follow.
const nextCursor = ref(null)
const loading = ref(false)
const loaded = ref(false)
// Whether the first page couldn't be loaded.
const failed = ref(false)
// The search the shown templates were loaded with.
const loadedSearch = ref('')

// Only the response of the latest request is used, so that a slow response of an
// older search or category can't replace the results of the current one.
let lastRequest = 0

/**
 * Loads the page after the cursor with the current search and category, the first
 * page without one, which replaces the shown templates.
 */
async function fetchPage(cursor = null) {
  const request = ++lastRequest
  const requestSearch = search.value
  loading.value = true
  try {
    const { data } = await TemplateService($client).fetchListed({
      cursor,
      limit: PAGE_SIZE,
      search: requestSearch,
      categoryId: categoryId.value,
    })
    if (request !== lastRequest) {
      return
    }
    templates.value =
      cursor === null ? data.results : [...templates.value, ...data.results]
    nextCursor.value = data.next_cursor
    loadedSearch.value = requestSearch
    failed.value = false
  } catch (error) {
    if (request === lastRequest) {
      // A failed first page shows the error instead of the list, the toast is
      // only for a failed next page.
      failed.value = cursor === null
      if (!failed.value) {
        notifyIf(error, 'templates')
      }
    }
  } finally {
    if (request === lastRequest) {
      loaded.value = true
      loading.value = false
    }
  }
}

// Like `lastRequest`, for the categories.
let lastCategoriesRequest = 0

// The sidebar stays empty when the categories can't be loaded.
async function fetchCategories() {
  const request = ++lastCategoriesRequest
  try {
    const { data } = await TemplateService($client).fetchListedCategories()
    if (request !== lastCategoriesRequest) {
      return
    }
    categories.value = data
    // The chosen category is gone once it holds no shared template, for example
    // after the user's template was made private, so all templates are shown.
    if (
      categoryId.value !== null &&
      !data.some(({ id }) => id === categoryId.value)
    ) {
      selectCategory(null)
    }
  } catch (error) {
    if (request === lastCategoriesRequest) {
      notifyIf(error, 'templates')
    }
  }
}

/**
 * Loads the categories and the first page again, for example after the user's
 * template was made private.
 */
function refresh() {
  fetchCategories()
  return fetchPage()
}

const searchChanged = debounce(() => fetchPage(), 300)

watch(search, searchChanged)

function selectCategory(id) {
  categoryId.value = id
  searchChanged.cancel()
  fetchPage()
}

function searchStarted({ event }) {
  event.preventDefault()
  searchInput.value?.focus()
}

function listenToSearch(active) {
  $priorityBus.$off('start-search', searchStarted)
  if (active) {
    $priorityBus.$on('start-search', $priorityBus.level.HIGH, searchStarted)
  }
}

onMounted(() => {
  fetchCategories()
  fetchPage()
  listenToSearch(props.active)
})
watch(() => props.active, listenToSearch)

onBeforeUnmount(() => {
  searchChanged.cancel()
  $priorityBus.$off('start-search', searchStarted)
})

defineExpose({ refresh })
</script>
