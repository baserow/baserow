<template>
  <!-- The frame is shared with the list of the official templates. -->
  <div class="template-list user-template-list">
    <div
      class="template-list__head"
      :class="{ 'template-list__head--centered': $slots.head }"
    >
      <slot name="head">
        <div class="template-list__title">
          {{ $t('userTemplateList.title') }}
        </div>
      </slot>
    </div>
    <div class="user-template-list__body">
      <div v-if="!loaded" class="user-template-list__loading">
        <div class="loading"></div>
      </div>
      <TemplateEmptyState
        v-else-if="failed"
        icon="iconoir-warning-triangle"
        :title="$t('userTemplateList.errorTitle')"
        :description="$t('userTemplateList.errorDescription')"
      >
        <Button type="secondary" :loading="loading" @click="refresh()">
          {{ $t('userTemplateList.retry') }}
        </Button>
      </TemplateEmptyState>
      <template v-else-if="isEmpty">
        <div class="user-template-list__title">
          {{ $t('userTemplateList.title') }}
        </div>
        <TemplateEmptyState
          icon="iconoir-box"
          :title="$t('userTemplateList.emptyTitle')"
          :description="
            createDisabledReason || $t('userTemplateList.emptyDescription')
          "
        >
          <Button
            v-if="!createDisabledReason"
            icon="iconoir-plus"
            @click="emit('create')"
          >
            {{ $t('userTemplateList.newTemplate') }}
          </Button>
        </TemplateEmptyState>
      </template>
      <template v-else>
        <div class="user-template-list__toolbar">
          <div class="user-template-list__title">
            {{ $t('userTemplateList.count', { count }) }}
          </div>
          <FormInput
            ref="searchInput"
            v-model="search"
            class="user-template-list__search"
            icon-left="iconoir-search"
            :placeholder="$t('userTemplateList.search')"
          ></FormInput>
          <span v-tooltip:[TOOLTIP_OPTIONS]="createDisabledReason || null">
            <Button
              icon="iconoir-plus"
              :disabled="!!createDisabledReason"
              @click="emit('create')"
            >
              {{ $t('userTemplateList.newTemplate') }}
            </Button>
          </span>
        </div>
        <TemplateEmptyState
          v-if="templates.length === 0"
          :query="loadedSearch"
        ></TemplateEmptyState>
        <div v-else class="user-template-list__table">
          <div class="user-template-list__row user-template-list__row--head">
            <div class="user-template-list__cell">
              {{ $t('userTemplateList.name') }}
            </div>
            <div class="user-template-list__cell">
              {{ $t('userTemplateList.visibility') }}
            </div>
            <div class="user-template-list__cell">
              {{ $t('userTemplateList.lastUpdated') }}
            </div>
            <div class="user-template-list__cell">
              {{ $t('userTemplateList.used') }}
            </div>
            <div class="user-template-list__cell"></div>
          </div>
          <InfiniteScroll
            class="user-template-list__scroll"
            :current-count="templates.length"
            :max-count="count"
            :page-size="PAGE_SIZE"
            :loading="loading"
            :render-end="false"
            @load-next-page="fetchNextPage"
          >
            <div
              v-for="template in templates"
              :key="template.id"
              class="user-template-list__row"
              @click="emit('selected', template)"
            >
              <!-- The name takes the keyboard, so that the actions button isn't
              nested in another interactive element. -->
              <div
                class="user-template-list__cell user-template-list__name"
                role="button"
                tabindex="0"
                @keydown.enter.prevent="emit('selected', template)"
                @keydown.space.prevent="emit('selected', template)"
              >
                <div class="user-template-list__icon">
                  <i :class="template.icon || 'iconoir-view-grid'"></i>
                </div>
                <div class="user-template-list__name-text">
                  <div class="user-template-list__name-title">
                    {{ template.name }}
                  </div>
                  <div
                    v-if="template.description"
                    class="user-template-list__description"
                  >
                    {{ template.description }}
                  </div>
                </div>
              </div>
              <div class="user-template-list__cell">
                <Badge
                  v-tooltip:[TOOLTIP_OPTIONS]="template.reason || null"
                  :color="getState(template).color"
                  rounded
                  >{{ getState(template).label }}</Badge
                >
              </div>
              <div class="user-template-list__cell user-template-list__updated">
                {{ getHumanAgoLabel($i18n.t, template.updated_on) }}
              </div>
              <div class="user-template-list__cell user-template-list__used">
                <i18n-t
                  keypath="userTemplateList.usedTimes"
                  :plural="template.install_count"
                  scope="global"
                  tag="span"
                >
                  <template #count>
                    <span class="user-template-list__used-count">{{
                      template.install_count
                    }}</span>
                  </template>
                </i18n-t>
              </div>
              <div class="user-template-list__cell user-template-list__actions">
                <ButtonIcon
                  type="secondary"
                  size="small"
                  icon="iconoir-more-vert"
                  :title="$t('userTemplateList.actions')"
                  @click.stop="toggleActions($event, template)"
                ></ButtonIcon>
              </div>
            </div>
          </InfiniteScroll>
          <Context ref="actionsContext" @hidden="focusedTemplate = null">
            <ul class="context__menu">
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  @click.prevent="edit('details')"
                >
                  <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                  {{ $t('userTemplateList.editDetails') }}
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  @click.prevent="edit('content')"
                >
                  <i class="context__menu-item-icon iconoir-refresh-double"></i>
                  {{ $t('userTemplateList.updateContent') }}
                </a>
              </li>
              <li class="context__menu-item context__menu-item--with-separator">
                <a
                  class="context__menu-item-link context__menu-item-link--delete"
                  @click.prevent="askToDelete()"
                >
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  {{ $t('userTemplateList.delete') }}
                </a>
              </li>
            </ul>
          </Context>
        </div>
      </template>
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
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import TemplateEmptyState from '@baserow/modules/core/components/template/TemplateEmptyState'

const PAGE_SIZE = 20

// The tooltips hold sentences, which don't fit in one line.
const TOOLTIP_OPTIONS = { contentClasses: 'tooltip__content--expandable' }

const STATES = {
  private: { color: 'neutral', label: 'userTemplateList.statePrivate' },
  in_review: { color: 'yellow', label: 'userTemplateList.stateInReview' },
  rejected: { color: 'red', label: 'userTemplateList.stateRejected' },
  blocked: { color: 'red', label: 'userTemplateList.stateBlocked' },
  public: { color: 'green', label: 'userTemplateList.statePublic' },
}

/**
 * A state that this version doesn't know is shown as it is, so that the list
 * still works when a new state is added.
 */
function getState(template) {
  const state = STATES[template.state]
  return state
    ? { color: state.color, label: $i18n.t(state.label) }
    : { color: 'neutral', label: template.state }
}

const props = defineProps({
  // Whether the list is shown. A hidden list must not claim the search shortcut,
  // because only the listener with the highest priority receives it.
  active: {
    type: Boolean,
    required: false,
    default: true,
  },
})

// `delete` asks to delete a template, which `remove` then drops from the list.
const emit = defineEmits(['selected', 'create', 'edit', 'delete'])

const { $client, $i18n, $priorityBus, $store } = useNuxtApp()

const searchInput = ref(null)
const actionsContext = ref(null)
// The template whose actions are shown.
const focusedTemplate = ref(null)
const search = ref('')
const templates = ref([])
const count = ref(0)
const loading = ref(false)
const loaded = ref(false)
// Whether the templates couldn't be loaded, while none are shown yet.
const failed = ref(false)
// The search the shown templates were loaded with.
const loadedSearch = ref('')

// Only the response of the latest request is used, so that a slow response of an
// older search can't replace the results of the current one.
let lastRequest = 0
// When the shown templates were last loaded, see `remove`.
let loadedAt = 0

// Nothing found without a search: the user hasn't created any template yet.
const isEmpty = computed(() => count.value === 0 && loadedSearch.value === '')

const workspaces = computed(() => $store.getters['workspace/getAll'])

// A template is created from a workspace with content. Explains why the user
// can't create one, or is null when they can. The permissions are only checked
// by the wizard, which fetches them.
const createDisabledReason = computed(() => {
  if (workspaces.value.length === 0) {
    return $i18n.t('userTemplateList.noWorkspace')
  }
  const hasContent = workspaces.value.some(
    (workspace) =>
      $store.getters['application/getAllOfWorkspace'](workspace).length > 0
  )
  return hasContent ? null : $i18n.t('userTemplateList.noContent')
})

async function fetchPage(offset, requestSearch = search.value) {
  const request = ++lastRequest
  loading.value = true
  try {
    const { data } = await TemplateService($client).fetchOwn({
      offset,
      limit: PAGE_SIZE,
      search: requestSearch,
    })
    if (request !== lastRequest) {
      return
    }
    templates.value =
      offset === 0 ? data.results : [...templates.value, ...data.results]
    count.value = data.count
    loadedSearch.value = requestSearch
    loadedAt = performance.now()
    failed.value = false
  } catch (error) {
    if (request === lastRequest) {
      notifyIf(error, 'templates')
      failed.value = failed.value || !loaded.value
    }
  } finally {
    if (request === lastRequest) {
      loaded.value = true
      loading.value = false
    }
  }
}

function fetchNextPage() {
  return fetchPage(templates.value.length, loadedSearch.value)
}

/**
 * Loads the first page again, for example after a template was created.
 */
function refresh() {
  return fetchPage(0)
}

/**
 * Opens the actions of a template next to the clicked button, or closes them when
 * they're already open for it.
 */
function toggleActions(event, template) {
  const open =
    actionsContext.value.isOpen() && focusedTemplate.value?.id === template.id
  focusedTemplate.value = template
  actionsContext.value.toggle(
    event.currentTarget,
    'bottom',
    'right',
    4,
    0,
    !open
  )
}

function edit(mode) {
  const template = focusedTemplate.value
  actionsContext.value.hide()
  emit('edit', template, mode)
}

function askToDelete() {
  const template = focusedTemplate.value
  actionsContext.value.hide()
  emit('delete', template)
}

/**
 * Drops a deleted template from the loaded ones without loading them again. When
 * it isn't loaded, for example because a refresh dropped the later pages, the first
 * page is loaded again so that the count is right. It's loaded again too while a
 * page loads, or when one was loaded after the deletion was requested, because that
 * page's offset and count might already account for the deleted template.
 *
 * @param {number} templateId The id of the deleted template.
 * @param {number} requestedAt The `performance.now()` at which the deletion was
 *   requested.
 */
function remove(templateId, requestedAt = performance.now()) {
  const index = templates.value.findIndex(({ id }) => id === templateId)
  const reload = index === -1 || loading.value || loadedAt >= requestedAt
  if (index !== -1) {
    templates.value.splice(index, 1)
    count.value = Math.max(count.value - 1, 0)
  }
  if (reload) {
    refresh()
  }
}

const searchChanged = debounce(() => fetchPage(0), 300)

watch(search, searchChanged)

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
  fetchPage(0)
  listenToSearch(props.active)
})
watch(() => props.active, listenToSearch)

onBeforeUnmount(() => {
  searchChanged.cancel()
  $priorityBus.$off('start-search', searchStarted)
})

defineExpose({ refresh, remove })
</script>
