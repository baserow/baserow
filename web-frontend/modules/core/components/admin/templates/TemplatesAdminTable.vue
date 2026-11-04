<template>
  <CrudTable
    :columns="columns"
    :service="service"
    row-id-key="id"
    :filters="filters"
    :enable-search="false"
    @review="showReviewModal"
    @reject="showRejectModal"
  >
    <template #title>
      {{ $t('templatesAdmin.title') }}
    </template>
    <template #subtitle>
      {{ $t('templatesAdmin.subtitle') }}
    </template>
    <template #no-results>
      <p>{{ $t(TABS[tabIndex].empty) }}</p>
    </template>
    <template #header-filters>
      <div class="templates-admin-tabs">
        <Tabs v-model:selected-index="tabIndex" header-no-padding>
          <Tab v-for="tab in tabs" :key="tab.state" :title="tab.title"></Tab>
        </Tabs>
      </div>
    </template>
    <template #menus="slotProps">
      <!-- Before the reject modal, which opens on top of it. -->
      <TemplateReviewModal
        ref="reviewModal"
        :template="reviewRow"
        :can-close="!rejecting"
        @reject="showRejectModal"
        @reviewed="reviewed(slotProps.refresh)"
      ></TemplateReviewModal>
      <RejectTemplateModal
        ref="rejectModal"
        :template="rejectRow"
        :edit-only="rejectRow.listed && rejectRow.state === 'in_review'"
        :unlist="rejectAction === 'unlist'"
        :request="(reason) => review(rejectRow, rejectAction, reason)"
        @done="reviewed(slotProps.refresh)"
        @hidden="rejecting = false"
      ></RejectTemplateModal>
    </template>
  </CrudTable>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplateReasonField from '@baserow/modules/core/components/admin/templates/fields/TemplateReasonField'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
import RejectTemplateModal from '@baserow/modules/core/components/admin/templates/RejectTemplateModal'
import TemplateReviewModal from '@baserow/modules/core/components/admin/templates/TemplateReviewModal'
import {
  rejectUnlists,
  useTemplateReview,
} from '@baserow/modules/core/composables/useTemplateReview'
import { notifyIf } from '@baserow/modules/core/utils/error'

// The tabs, one per state of the templates on the page, with the locale keys of
// their name and of the text shown when they're empty.
const TABS = [
  {
    state: 'in_review',
    name: 'templatesAdmin.inReview',
    empty: 'templatesAdmin.inReviewEmpty',
  },
  {
    state: 'public',
    name: 'templatesAdmin.published',
    empty: 'templatesAdmin.publishedEmpty',
  },
  {
    state: 'rejected',
    name: 'templatesAdmin.rejectedTab',
    empty: 'templatesAdmin.rejectedEmpty',
  },
]

const { $client, $i18n } = useNuxtApp()

const service = TemplatesAdminService($client)
const { review } = useTemplateReview()
const tabIndex = ref(0)
// The number of templates by state, null until loaded.
const counts = ref(null)
// The rows that the review and reject modals are for. The modals are the
// table's, not the row's, as the row is unmounted when the list is refreshed
// after a review.
const reviewRow = ref({})
const reviewModal = ref(null)
const rejectRow = ref({})
// While the reject modal is open, also on top of the review modal.
const rejecting = ref(false)
// Rejecting a listed template unlists it.
const rejectAction = computed(() =>
  rejectUnlists(rejectRow.value) ? 'unlist' : 'reject'
)
const rejectModal = ref(null)

const state = computed(() => TABS[tabIndex.value].state)
const filters = computed(() => ({ state: state.value }))

const tabs = computed(() =>
  TABS.map(({ state, name }) => ({
    state,
    title: counts.value
      ? $i18n.t('templatesAdmin.tabCount', {
          name: $i18n.t(name),
          count: counts.value[state],
        })
      : $i18n.t(name),
  }))
)

/**
 * Fetches the counts of the tabs. Only a review changes them, which moves a
 * template to another tab, so they're fetched on load, on tab change and after
 * a review, not when the page or the sorting of the list changes.
 */
async function fetchCounts() {
  try {
    const { data } = await service.counts()
    counts.value = data
  } catch (error) {
    notifyIf(error, 'template')
  }
}

onMounted(fetchCounts)
watch(tabIndex, fetchCounts)

function showReviewModal(row) {
  reviewRow.value = row
  reviewModal.value.show()
}

function showRejectModal(row) {
  rejectRow.value = row
  rejecting.value = true
  rejectModal.value.show()
}

/**
 * Closes the preview and refreshes the list and the counts once a template was
 * approved, rejected or unlisted, or the server refused because the template
 * changed since.
 */
function reviewed(refresh) {
  reviewModal.value.hide()
  refresh()
  fetchCounts()
}

const columns = computed(() => [
  new CrudTableColumn(
    'name',
    () => $i18n.t('templatesAdmin.template'),
    TemplateNameField,
    true,
    true
  ),
  new CrudTableColumn(
    'author',
    () => $i18n.t('templatesAdmin.author'),
    TemplateAuthorField,
    true
  ),
  state.value === 'rejected'
    ? new CrudTableColumn(
        'reason',
        () => $i18n.t('templatesAdmin.reason'),
        TemplateReasonField
      )
    : new CrudTableColumn(
        'updated_on',
        () => $i18n.t('templatesAdmin.updatedOn'),
        LocalDateField,
        true
      ),
  new CrudTableColumn(
    'actions',
    '',
    TemplateReviewActionsField,
    false,
    false,
    true
  ),
])
</script>
