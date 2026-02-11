<template>
  <div class="audit-log__table">
    <AuditLogExportModal
      ref="exportModal"
      :filters="filters"
      :workspace-id="workspaceId"
    ></AuditLogExportModal>
    <CrudTable
      :columns="columns"
      :filters="filters"
      :default-column-sorts="[{ key: 'timestamp', direction: 'asc' }]"
      :service="service"
      :enable-search="false"
      row-id-key="id"
    >
      <template #title>
        {{
          workspaceId
            ? $t('auditLog.workspaceTitle', { workspaceName })
            : $t('auditLog.adminTitle')
        }}
      </template>
      <template #header-right-side>
        <Button
          type="primary"
          size="large"
          @click.prevent="exportModal?.show()"
        >
          {{ $t('auditLog.exportToCsv') }}</Button
        >
      </template>
      <template #header-filters>
        <div
          class="audit-log__filters"
          :class="{ 'audit-log__filters--workspace': workspaceId }"
        >
          <FilterWrapper :name="$t('auditLog.filterUserTitle')">
            <PaginatedDropdown
              ref="userFilter"
              :value="filters.user_id"
              :fetch-page="fetchUsers"
              :empty-item-display-name="$t('auditLog.allUsers')"
              :not-selected-text="$t('auditLog.allUsers')"
              @input="filterUser"
            ></PaginatedDropdown>
          </FilterWrapper>
          <FilterWrapper
            v-if="!workspaceId"
            :name="$t('auditLog.filterWorkspaceTitle')"
          >
            <PaginatedDropdown
              ref="workspaceFilter"
              :value="filters.workspace_id"
              :fetch-page="fetchWorkspaces"
              :empty-item-display-name="$t('auditLog.allWorkspaces')"
              :not-selected-text="$t('auditLog.allWorkspaces')"
              @input="filterWorkspace"
            ></PaginatedDropdown>
          </FilterWrapper>
          <FilterWrapper :name="$t('auditLog.filterActionTypeTitle')">
            <PaginatedDropdown
              ref="typeFilter"
              :value="filters.action_type"
              :fetch-page="fetchActionTypes"
              :empty-item-display-name="$t('auditLog.allActionTypes')"
              :not-selected-text="$t('auditLog.allActionTypes')"
              @input="filterActionType"
            ></PaginatedDropdown>
          </FilterWrapper>
          <FilterWrapper :name="$t('auditLog.filterFromTimestampTitle')">
            <DateFilter
              ref="fromTimestampFilter"
              :placeholder="$t('auditLog.filterFromTimestamp')"
              :disable-dates="disableDates"
              @input="filterFromTimestamp"
            ></DateFilter>
          </FilterWrapper>
          <FilterWrapper :name="$t('auditLog.filterToTimestampTitle')">
            <DateFilter
              ref="toTimestampFilter"
              :placeholder="$t('auditLog.filterToTimestamp')"
              :disable-dates="disableDates"
              @input="filterToTimestamp"
            ></DateFilter>
          </FilterWrapper>
          <Button
            class="audit-log__clear-filters-button"
            type="secondary"
            @click="clearFilters"
          >
            {{ $t('auditLog.clearFilters') }}</Button
          >
        </div>
      </template>
    </CrudTable>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useStore } from 'vuex'
import {
  useRoute,
  useRouter,
  useNuxtApp,
  createError,
  definePageMeta,
  useI18n,
  useHead,
} from '#imports'
import _ from 'lodash'
import moment from '@baserow/modules/core/moment'

// Components
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import DateFilter from '@baserow_enterprise/components/crudTable/filters/DateFilter'
import FilterWrapper from '@baserow_enterprise/components/crudTable/filters/FilterWrapper'
import AuditLogExportModal from '@baserow_enterprise/components/admin/modals/AuditLogExportModal'

// Services & utilities
import AuditLogService from '@baserow_enterprise/services/auditLog'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import LongTextField from '@baserow_enterprise/components/crudTable/fields/LongTextField'
import EnterpriseFeatures from '@baserow_enterprise/features'

// Page meta
definePageMeta({
  layout: 'app',
  middleware: 'authenticated',
})

// Composables
const store = useStore()
const route = useRoute()
const router = useRouter()
const { $client, $hasFeature, $hasPermission } = useNuxtApp()
const { t: $t } = useI18n()

useHead({ title: $t('auditLog.adminTitle') })

// Helper function
function initFilters(wsId = null) {
  const f = {}
  if (wsId !== null) {
    f.workspace_id = wsId
  }
  return f
}

// Parse workspaceId from route
const workspaceId = route.params.workspaceId
  ? parseInt(route.params.workspaceId)
  : null

// Permission checks (equivalent to asyncData)
if (workspaceId) {
  if (!$hasFeature(EnterpriseFeatures.AUDIT_LOG, workspaceId)) {
    throw createError({
      statusCode: 401,
      message: 'Available in the advanced/enterprise version',
    })
  } else if (
    !$hasPermission(
      'workspace.list_audit_log_entries',
      store.getters['workspace/get'](workspaceId),
      workspaceId
    )
  ) {
    throw createError({ statusCode: 404, message: 'Page not found' })
  }
} else if (!$hasFeature(EnterpriseFeatures.AUDIT_LOG)) {
  throw createError({
    statusCode: 401,
    message: 'Available in the advanced/enterprise version',
  })
} else if (!store.getters['auth/isStaff']) {
  throw createError({ statusCode: 403, message: 'Forbidden.' })
}

// Template refs
const exportModal = ref(null)
const userFilter = ref(null)
const workspaceFilter = ref(null)
const typeFilter = ref(null)
const fromTimestampFilter = ref(null)
const toTimestampFilter = ref(null)

// Reactive state
const filters = ref(initFilters(workspaceId))
const dateTimeFormat = 'YYYY-MM-DDTHH:mm:ss.SSSZ'

// Build columns
const columns = [
  new CrudTableColumn(
    'user',
    () => $t('auditLog.user'),
    SimpleField,
    true,
    false,
    false,
    {},
    '15'
  ),
]

if (!workspaceId) {
  columns.push(
    new CrudTableColumn(
      'workspace',
      () => $t('auditLog.workspace'),
      SimpleField,
      true,
      false,
      false,
      {},
      '15'
    )
  )
}

columns.push(
  new CrudTableColumn(
    'type',
    () => $t('auditLog.actionType'),
    SimpleField,
    true,
    false,
    false,
    {},
    '10'
  ),
  new CrudTableColumn(
    'description',
    () => $t('auditLog.description'),
    LongTextField,
    false,
    false,
    false,
    {},
    '40'
  ),
  new CrudTableColumn(
    'timestamp',
    () => $t('auditLog.timestamp'),
    LocalDateField,
    true,
    false,
    false,
    { dateTimeFormat: 'L LTS' },
    '10'
  ),
  new CrudTableColumn(
    'ip_address',
    () => $t('auditLog.ip_address'),
    SimpleField,
    true,
    false,
    false,
    {},
    '10'
  )
)

// Service
const service = AuditLogService($client)

// Computed
const workspaceName = computed(() => {
  const ws = store.getters['workspace/get'](workspaceId)
  return ws ? ws.name : ''
})

const disableDates = computed(() => {
  const minimumDate = moment('2023-01-01', 'YYYY-MM-DD')
  const maximumDate = moment().add(1, 'day').endOf('day')
  return {
    to: minimumDate.toDate(),
    from: maximumDate.toDate(),
  }
})

const selectedWorkspaceId = computed(() => {
  const selected = store.getters['workspace/getSelected']
  return selected?.id || null
})

// Watch
watch(selectedWorkspaceId, (newValue, oldValue) => {
  if (newValue !== oldValue && workspaceId) {
    router.push({
      name: newValue ? 'workspace-audit-log' : 'dashboard',
      params: { workspaceId: newValue },
    })
  }
})

// Methods
function setFilter(key, value) {
  if (value == null) {
    if (filters.value[key] !== undefined) {
      filters.value = _.pickBy(filters.value, (v, k) => k !== key)
    }
  } else {
    filters.value = { ...filters.value, [key]: value }
  }
}

function clearFilters() {
  userFilter.value?.clear()
  workspaceFilter.value?.clear()
  typeFilter.value?.clear()
  fromTimestampFilter.value?.clear()
  toTimestampFilter.value?.clear()
  filters.value = initFilters(workspaceId)
}

function filterUser(userId) {
  setFilter('user_id', userId)
}

function fetchUsers(page, search) {
  return service.fetchUsers(page, search, workspaceId)
}

function filterWorkspace(wsId) {
  setFilter('workspace_id', wsId)
}

function fetchWorkspaces(page, search) {
  return service.fetchWorkspaces(page, search)
}

function fetchActionTypes(page, search) {
  return service.fetchActionTypes(page, search, workspaceId)
}

function filterActionType(actionTypeId) {
  setFilter('action_type', actionTypeId)
}

function filterFromTimestamp(fromTimestamp) {
  if (fromTimestamp && moment(fromTimestamp).isValid()) {
    setFilter(
      'from_timestamp',
      moment(fromTimestamp).startOf('day').format(dateTimeFormat)
    )
  } else if (!fromTimestamp) {
    setFilter('from_timestamp', null)
  }
}

function filterToTimestamp(toTimestamp) {
  if (toTimestamp && moment(toTimestamp).isValid()) {
    setFilter(
      'to_timestamp',
      moment(toTimestamp).endOf('day').format(dateTimeFormat)
    )
  } else if (!toTimestamp) {
    setFilter('to_timestamp', null)
  }
}
</script>
