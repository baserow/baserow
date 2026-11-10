<template>
  <CrudTable
    ref="crudTable"
    :columns="columns"
    :service="service"
    row-id-key="id"
    :filters="filters"
    :search-placeholder="$t('templatesAdmin.searchPlaceholder')"
    @open-review="showReviewModal"
    @row-context="onRowContext"
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
        <Tabs
          v-model:selected-index="tabIndex"
          header-no-padding
          content-no-padding
        >
          <Tab v-for="tab in tabs" :key="tab.state" :title="tab.title"></Tab>
        </Tabs>
      </div>
    </template>
    <template #menus="slotProps">
      <!-- Before the reject modal, which opens on top of it. -->
      <TemplateReviewModal
        ref="reviewModal"
        :template="reviewRow"
        :preview-only="previewing"
        :can-close="!rejecting"
        @reject="showRejectModal"
        @reviewed="(id) => reviewed(slotProps.refresh, id)"
      ></TemplateReviewModal>
      <RejectTemplateModal
        ref="rejectModal"
        :template="rejectRow"
        :block="blocking"
        :request="reject"
        @done="(id) => reviewed(slotProps.refresh, id)"
        @hidden="rejectHidden"
      ></RejectTemplateModal>
      <TemplateAdminContext
        ref="adminContext"
        :template="contextRow"
        @view="showInTemplates"
        @preview="showPreviewModal"
        @unlist="showRejectModal"
        @block="showBlockModal"
        @delete="showDeleteModal"
        @changed="(id) => reviewed(slotProps.refresh, id)"
      ></TemplateAdminContext>
      <DeleteUserTemplateModal
        ref="deleteModal"
        :template="deletedRow"
        @deleted="(id) => deleted(id, slotProps)"
      ></DeleteUserTemplateModal>
      <TemplateModal ref="templateModal"></TemplateModal>
    </template>
  </CrudTable>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplateReasonField from '@baserow/modules/core/components/admin/templates/fields/TemplateReasonField'
import TemplateSubmittedField from '@baserow/modules/core/components/admin/templates/fields/TemplateSubmittedField'
import TemplateUsedField from '@baserow/modules/core/components/admin/templates/fields/TemplateUsedField'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
import RejectTemplateModal from '@baserow/modules/core/components/admin/templates/RejectTemplateModal'
import TemplateReviewModal from '@baserow/modules/core/components/admin/templates/TemplateReviewModal'
import TemplateAdminContext from '@baserow/modules/core/components/admin/templates/contexts/TemplateAdminContext'
import DeleteUserTemplateModal from '@baserow/modules/core/components/template/DeleteUserTemplateModal'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'
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
  {
    state: 'blocked',
    name: 'templatesAdmin.blockedTab',
    empty: 'templatesAdmin.blockedEmpty',
  },
]

const { $client, $i18n, $store } = useNuxtApp()

const service = TemplatesAdminService($client)
const { decide } = useTemplateReview()
const crudTable = ref(null)
const tabIndex = ref(0)
const counts = computed(() => $store.getters['templatesAdmin/counts'])
const reviewRow = ref({})
const previewing = ref(false)
const reviewModal = ref(null)
const rejectRow = ref({})
const rejecting = ref(false)
const blocking = ref(false)
const rejectModal = ref(null)
const contextRow = ref(null)
const adminContext = ref(null)
const deletedRow = ref({})
const deleteModal = ref(null)
const templateModal = ref(null)

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

async function fetchCounts({ force = false } = {}) {
  try {
    await $store.dispatch('templatesAdmin/fetchCounts', { force })
  } catch (error) {
    notifyIf(error, 'template')
  }
}

onMounted(() => fetchCounts())
watch(tabIndex, () => fetchCounts())

function showReviewModal(row) {
  if (rejecting.value) {
    return
  }
  reviewRow.value = row
  previewing.value = false
  reviewModal.value.show()
}

function showPreviewModal(row) {
  reviewRow.value = row
  previewing.value = true
  reviewModal.value.show()
}

function reject(template, reason) {
  if (blocking.value) {
    return decide(template, 'block', reason)
  }
  return decide(template, template.reject_unlists ? 'unlist' : 'reject', reason)
}

function showRejectModal(row, { block = false } = {}) {
  if (rejecting.value) {
    return
  }
  rejectRow.value = row
  blocking.value = block
  rejecting.value = true
  rejectModal.value.show()
}

function showBlockModal(row) {
  showRejectModal(row, { block: true })
}

async function rejectHidden() {
  rejecting.value = false
  await nextTick()
  reviewModal.value.focusReject()
}

/**
 * Opens the menu of the row next to its button, or at the pointer for a right
 * click, or closes it when it's already open for the row.
 */
function onRowContext({ row, event, target }) {
  event.preventDefault()
  if (target === undefined) {
    target = { left: event.clientX, top: event.clientY }
  }
  const action = row.id === contextRow.value?.id ? 'toggle' : 'show'
  contextRow.value = row
  adminContext.value[action](target, 'bottom', 'right', 4)
}

function showInTemplates(row) {
  templateModal.value.showShared(row.name)
}

function showDeleteModal(row) {
  deletedRow.value = row
  deleteModal.value.show()
}

/**
 * Drops the deleted template from the list right away, then refreshes the list
 * and the counts, also when it was already deleted, for example by its author.
 */
function deleted(id, { deleteRow, refresh }) {
  deleteRow(id)
  reviewed(refresh, id)
}

async function reviewed(refresh, id) {
  if (reviewRow.value.id === id) {
    reviewModal.value.hide()
  }
  const refreshed = refresh()
  fetchCounts({ force: true })
  await refreshed
  await focusRow(id)
}

async function focusRow(id) {
  await nextTick()
  if (document.activeElement && document.activeElement !== document.body) {
    return
  }
  const button = crudTable.value?.$el.querySelector(
    `[data-template-id="${id}"] button`
  )
  if (button) {
    button.focus()
  } else {
    crudTable.value?.focus()
  }
}

const STATE_COLUMNS = {
  in_review: () =>
    new CrudTableColumn(
      'submitted',
      () => $i18n.t('templatesAdmin.submitted'),
      TemplateSubmittedField,
      true
    ),
  public: () =>
    new CrudTableColumn(
      'used',
      () => $i18n.t('templatesAdmin.used'),
      TemplateUsedField,
      true
    ),
  rejected: reasonColumn,
  blocked: reasonColumn,
}

function reasonColumn() {
  return new CrudTableColumn(
    'reason',
    () => $i18n.t('templatesAdmin.reason'),
    TemplateReasonField
  )
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
  STATE_COLUMNS[state.value](),
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
