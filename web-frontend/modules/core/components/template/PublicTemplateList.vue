<template>
  <!-- The frame and the sidebar are shared with the list of the official
  templates. -->
  <div class="template-list public-template-list">
    <div
      class="template-list__head"
      :class="{ 'template-list__head--centered': $slots.head }"
    >
      <slot name="head">
        <div class="template-list__title">
          {{ $t('publicTemplateList.title') }}
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
      <div class="public-template-list__content">
        <div v-if="!loaded" class="public-template-list__loading">
          <div class="loading"></div>
        </div>
        <TemplateEmptyState
          v-else-if="failed"
          icon="iconoir-warning-triangle"
          :title="$t('publicTemplateList.errorTitle')"
          :description="$t('publicTemplateList.errorDescription')"
        >
          <Button type="secondary" :loading="loading" @click="fetchPage()">
            {{ $t('publicTemplateList.retry') }}
          </Button>
        </TemplateEmptyState>
        <TemplateEmptyState
          v-else-if="templates.length === 0"
          icon="iconoir-group"
          :query="loadedSearch"
          :title="
            categoryId === null
              ? $t('publicTemplateList.emptyTitle')
              : $t('publicTemplateList.emptyCategoryTitle')
          "
          :description="$t('publicTemplateList.emptyDescription')"
        ></TemplateEmptyState>
        <InfiniteScroll
          v-else
          class="public-template-list__scroll"
          :current-count="templates.length"
          :has-more-page="hasNextPage"
          :page-size="PAGE_SIZE"
          :loading="loading"
          :render-end="false"
          fill
          @load-next-page="fetchPage(offset)"
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
              <div class="public-template-list__card-footer">
                <div
                  v-if="template.author_name"
                  class="public-template-list__author"
                >
                  <Avatar
                    :initials="template.author_name.charAt(0).toUpperCase()"
                    size="small"
                    rounded
                  ></Avatar>
                  <span
                    class="public-template-list__author-name"
                    :title="template.author_name"
                    >{{
                      isOwnTemplate(template)
                        ? $t('publicTemplateList.you')
                        : template.author_name
                    }}</span
                  >
                </div>
                <div
                  v-if="template.updated_on"
                  class="public-template-list__updated"
                  :title="updatedLabel($t, template.updated_on)"
                >
                  {{ updatedLabel($t, template.updated_on) }}
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
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'
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

// Shown on hover too, because the date is cut when the card is narrow.
const updatedLabel = (t, updatedOn) =>
  t('publicTemplateList.updated', { ago: getHumanAgoLabel(t, updatedOn) })

// The categories holding a public template.
const categories = ref([])
const searchInput = ref(null)
const search = ref('')
const categoryId = ref(null)
const templates = ref([])
// Where the next page starts: the number of templates received so far, which is
// more than the shown ones when a template moved to the next page meanwhile.
const offset = ref(0)
const hasNextPage = ref(false)
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
 * Loads the page at the offset with the current search and category. The first
 * page replaces the shown templates.
 */
async function fetchPage(pageOffset = 0) {
  const request = ++lastRequest
  const requestSearch = search.value
  loading.value = true
  try {
    const { data } = await TemplateService($client).fetchListed({
      offset: pageOffset,
      limit: PAGE_SIZE,
      search: requestSearch,
      categoryId: categoryId.value,
    })
    if (request !== lastRequest) {
      return
    }
    if (pageOffset === 0) {
      templates.value = data.results
    } else {
      // A template that moved to this page meanwhile, for example because one
      // before it was made private, is shown once.
      const shown = new Set(templates.value.map(({ id }) => id))
      templates.value = [
        ...templates.value,
        ...data.results.filter(({ id }) => !shown.has(id)),
      ]
    }
    offset.value = pageOffset + data.results.length
    hasNextPage.value = data.next !== null
    loadedSearch.value = requestSearch
    failed.value = false
  } catch (error) {
    if (request === lastRequest) {
      // A failed first page shows the error instead of the list, the toast is
      // only for a failed next page.
      failed.value = pageOffset === 0
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
    const { data } = await TemplateService($client).fetchPublicCategories()
    if (request !== lastCategoriesRequest) {
      return
    }
    categories.value = data
    // The chosen category is gone once it holds no public template, for example
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
watch(
  () => props.active,
  (active) => listenToSearch(active)
)

onBeforeUnmount(() => {
  searchChanged.cancel()
  $priorityBus.$off('start-search', searchStarted)
})

defineExpose({ refresh })
</script>
