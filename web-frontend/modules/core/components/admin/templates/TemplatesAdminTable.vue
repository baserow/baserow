<template>
  <CrudTable
    :columns="columns"
    :service="service"
    row-id-key="id"
    :filters="filters"
    :enable-search="false"
    @open-review="showReviewModal"
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
        @reviewed="(id) => reviewed(slotProps.refresh, id)"
      ></TemplateReviewModal>
      <RejectTemplateModal
        ref="rejectModal"
        :template="rejectRow"
        :request="reject"
        @done="(id) => reviewed(slotProps.refresh, id)"
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
import { useTemplateReview } from '@baserow/modules/core/composables/useTemplateReview'
import { notifyIf } from '@baserow/modules/core/utils/error'

const TABS = [
  {
    state: 'in_review',
    name: 'templatesAdmin.inReview',
    empty: 'templatesAdmin.inReviewEmpty',
  },
  {
    state: 'public',
    name: 'templatesAdmin.public',
    empty: 'templatesAdmin.publicEmpty',
  },
  {
    state: 'rejected',
    name: 'templatesAdmin.rejectedTab',
    empty: 'templatesAdmin.rejectedEmpty',
  },
]

const { $client, $i18n } = useNuxtApp()

const service = TemplatesAdminService($client)
const { decide } = useTemplateReview()
const tabIndex = ref(0)
const counts = ref(null)
// Kept here, not in the row field: the refresh after a review unmounts the rows.
const reviewRow = ref({})
const reviewModal = ref(null)
const rejectRow = ref({})
const rejecting = ref(false)
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
 * Fetches the tab counts. Not on page or sort changes, which don't move
 * templates between tabs.
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

// Rows behind the reject modal stay keyboard-reachable, so they can't open the
// preview or change the reject modal's template.
function showReviewModal(row) {
  if (rejecting.value) {
    return
  }
  reviewRow.value = row
  reviewModal.value.show()
}

function reject(template, reason) {
  return decide(template, template.reject_unlists ? 'unlist' : 'reject', reason)
}

function showRejectModal(row) {
  if (rejecting.value) {
    return
  }
  rejectRow.value = row
  rejecting.value = true
  rejectModal.value.show()
}

/**
 * Refreshes the list and counts after a review. Closes the preview only if it
 * still shows that template: the admin can open another one while a request
 * runs.
 *
 * @param {Function} refresh Refreshes the list of the table.
 * @param {number} id The id of the reviewed template.
 */
function reviewed(refresh, id) {
  if (reviewRow.value.id === id) {
    reviewModal.value.hide()
  }
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
