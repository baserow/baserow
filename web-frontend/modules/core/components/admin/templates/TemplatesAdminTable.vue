<template>
  <CrudTable
    :columns="columns"
    :service="service"
    row-id-key="id"
    :filters="filters"
    :enable-search="false"
    @total-count-update="fetchCounts"
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
  </CrudTable>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'
import TemplateNameField from '@baserow/modules/core/components/admin/templates/fields/TemplateNameField'
import TemplateAuthorField from '@baserow/modules/core/components/admin/templates/fields/TemplateAuthorField'
import TemplateReasonField from '@baserow/modules/core/components/admin/templates/fields/TemplateReasonField'
import TemplateReviewActionsField from '@baserow/modules/core/components/admin/templates/fields/TemplateReviewActionsField'
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
const tabIndex = ref(0)
// The number of templates by state, null until loaded.
const counts = ref(null)

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
 * Refreshes the counts of the tabs whenever the list is loaded, as a review moves
 * a template to another tab.
 */
async function fetchCounts() {
  try {
    const { data } = await service.counts()
    counts.value = data
  } catch (error) {
    notifyIf(error, 'template')
  }
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
