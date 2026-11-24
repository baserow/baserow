<template>
  <div
    v-if="featureFlagEnabled && (!hasFeature || canRead)"
    class="automatic-snapshots-settings"
  >
    <header class="automatic-snapshots-settings__header">
      <div class="automatic-snapshots-settings__header-text">
        <h3 class="automatic-snapshots-settings__title">
          {{ $t('automaticSnapshotsSettings.title') }}
        </h3>
        <p class="automatic-snapshots-settings__intro">
          {{ $t('automaticSnapshotsSettings.intro') }}
        </p>
      </div>
    </header>

    <section v-if="!hasFeature" class="automatic-snapshot-schedule">
      <div class="automatic-snapshot-schedule__main">
        <div
          class="automatic-snapshot-schedule__icon automatic-snapshot-schedule__icon--neutral"
        >
          <i class="iconoir-lock"></i>
        </div>
        <div class="automatic-snapshot-schedule__body">
          <div class="automatic-snapshot-schedule__head">
            <h3 class="automatic-snapshot-schedule__title">
              {{ $t('automaticSnapshotsSettings.workspaceSchedule') }}
            </h3>
            <Badge color="cyan" size="small" rounded>
              {{ $t('automaticSnapshots.enterpriseBadge') }}
            </Badge>
          </div>
          <div class="automatic-snapshot-schedule__description">
            {{ $t('automaticSnapshotsSettings.upsell') }}
          </div>
          <div class="automatic-snapshot-schedule__inline-actions">
            <Button
              type="secondary"
              size="small"
              @click="paidFeaturesModal.show()"
              >{{ $t('automaticSnapshots.learnMore') }}</Button
            >
          </div>
        </div>
      </div>
      <PaidFeaturesModal
        ref="paidFeaturesModal"
        :workspace="workspace"
        initial-selected-type="automatic_snapshots"
      ></PaidFeaturesModal>
    </section>

    <div v-else-if="loading" class="loading"></div>

    <div
      v-else-if="loadFailed"
      class="automatic-snapshots-settings__load-failed"
    >
      <span>{{ $t('automaticSnapshots.loadFailed') }}</span>
      <Button type="secondary" size="small" @click="load">{{
        $t('action.retry')
      }}</Button>
    </div>

    <template v-else-if="data">
      <section
        class="automatic-snapshot-schedule"
        :class="{ 'automatic-snapshot-schedule--empty': !workspaceDefault }"
      >
        <div class="automatic-snapshot-schedule__main">
          <div
            class="automatic-snapshot-schedule__icon"
            :class="
              workspaceDefault && workspaceDefault.enabled
                ? 'automatic-snapshot-schedule__icon--blue'
                : 'automatic-snapshot-schedule__icon--neutral'
            "
          >
            <i class="iconoir-clock"></i>
          </div>
          <div class="automatic-snapshot-schedule__body">
            <div class="automatic-snapshot-schedule__head">
              <h3 class="automatic-snapshot-schedule__title">
                {{ $t('automaticSnapshotsSettings.workspaceSchedule') }}
              </h3>
              <Badge
                v-if="workspaceDefault && !workspaceDefault.enabled"
                color="neutral"
                size="small"
                >{{ $t('automaticSnapshots.badgeOff') }}</Badge
              >
            </div>
            <template v-if="workspaceDefault && workspaceDefault.enabled">
              <div class="automatic-snapshot-schedule__schedule">
                {{ describe(workspaceDefault) }}
                <span
                  v-if="showsTimezone(workspaceDefault)"
                  class="automatic-snapshot-schedule__timezone"
                  >· {{ workspaceDefault.timezone }}</span
                >
              </div>
              <div class="automatic-snapshot-schedule__detail">
                {{ workspaceDefaultDetail }}
              </div>
            </template>
            <div v-else class="automatic-snapshot-schedule__description">
              {{
                workspaceDefault
                  ? $t('automaticSnapshotsSettings.workspaceScheduleOff')
                  : $t('automaticSnapshotsSettings.workspaceScheduleNone')
              }}
            </div>
            <div
              v-if="!workspaceDefault && canUpdateWorkspace"
              class="automatic-snapshot-schedule__inline-actions"
            >
              <Button size="small" @click="openWorkspaceForm()">{{
                $t('automaticSnapshotsSettings.setUpWorkspace')
              }}</Button>
            </div>
          </div>
          <SwitchInput
            v-if="workspaceDefault && canUpdateWorkspace"
            small
            role="switch"
            :tabindex="actionLoading ? -1 : 0"
            :aria-checked="workspaceDefault.enabled ? 'true' : 'false'"
            :aria-disabled="actionLoading ? 'true' : undefined"
            :value="workspaceDefault.enabled"
            :disabled="actionLoading"
            :aria-label="$t('automaticSnapshotsSettings.workspaceSchedule')"
            @input="toggleWorkspaceDefault"
            @keydown.enter.prevent="
              !actionLoading &&
              toggleWorkspaceDefault(!workspaceDefault.enabled)
            "
            @keydown.space.prevent="
              !actionLoading &&
              toggleWorkspaceDefault(!workspaceDefault.enabled)
            "
          ></SwitchInput>
        </div>

        <div
          v-if="workspaceDefault && canUpdateWorkspace"
          class="automatic-snapshot-schedule__footer"
        >
          <Button type="secondary" size="small" @click="openWorkspaceForm()">{{
            $t('automaticSnapshots.edit')
          }}</Button>
          <ButtonText
            :loading="actionLoading"
            @click="deleteWorkspaceDefault"
            >{{ $t('automaticSnapshotsSettings.removeWorkspace') }}</ButtonText
          >
        </div>
      </section>

      <section class="automatic-snapshots-settings__applications">
        <div class="automatic-snapshots-settings__applications-head">
          <h3 class="automatic-snapshot-schedule__title">
            {{ $t('automaticSnapshotsSettings.applications') }}
            <span class="automatic-snapshots-settings__muted">{{
              rows.length
            }}</span>
          </h3>
          <FormInput
            v-if="rows.length > 0"
            v-model="search"
            class="automatic-snapshots-settings__search"
            icon-left="iconoir-search"
            :placeholder="$t('automaticSnapshotsSettings.searchPlaceholder')"
          />
        </div>
        <div
          v-if="selectedIds.length > 0"
          class="automatic-snapshots-settings__bulk"
        >
          <span class="automatic-snapshots-settings__muted">{{
            $t('automaticSnapshotsSettings.selected', {
              count: selectedIds.length,
            })
          }}</span>
          <Button type="secondary" size="small" @click="openBulkForm">{{
            $t('automaticSnapshotsSettings.applySchedule')
          }}</Button>
          <Button
            type="secondary"
            size="small"
            :loading="actionLoading"
            @click="bulkReset"
            >{{ resetLabel }}</Button
          >
          <ButtonText @click="selectedIds = []">{{
            $t('automaticSnapshotsSettings.clearSelection')
          }}</ButtonText>
        </div>

        <div
          v-if="filteredRows.length > 0"
          class="automatic-snapshots-settings__table-wrapper"
        >
          <table class="automatic-snapshots-settings__table">
            <thead>
              <tr>
                <th class="automatic-snapshots-settings__check">
                  <Checkbox
                    :checked="allSelected"
                    :disabled="editableRows.length === 0"
                    :aria-label="$t('automaticSnapshotsSettings.selectAll')"
                    @input="toggleAll"
                  ></Checkbox>
                </th>
                <th>
                  {{ $t('automaticSnapshotsSettings.columnApplication') }}
                </th>
                <th class="automatic-snapshots-settings__follows-column">
                  {{ $t('automaticSnapshotsSettings.columnFollows') }}
                </th>
                <th class="automatic-snapshots-settings__schedule-column">
                  {{ $t('automaticSnapshotsSettings.columnSchedule') }}
                </th>
                <th class="automatic-snapshots-settings__menu-column">
                  <span class="automatic-snapshots-settings__visually-hidden">{{
                    $t('automaticSnapshotsSettings.columnActions')
                  }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in pagedRows" :key="row.application_id">
                <tr
                  :class="{
                    'automatic-snapshots-settings__row--with-warning':
                      row.blockedWarning,
                  }"
                >
                  <td class="automatic-snapshots-settings__check">
                    <Checkbox
                      :checked="selectedIds.includes(row.application_id)"
                      :disabled="!row.editable"
                      :aria-label="row.application_name"
                      @input="toggleRow(row)"
                    ></Checkbox>
                  </td>
                  <td>
                    <div class="automatic-snapshots-settings__application">
                      <i :class="row.iconClass"></i>
                      <span
                        class="automatic-snapshots-settings__application-name"
                        :title="row.application_name"
                        >{{ row.application_name }}</span
                      >
                    </div>
                  </td>
                  <td>
                    <Badge :color="row.badge.color" size="small">{{
                      row.badge.label
                    }}</Badge>
                  </td>
                  <td>
                    <div class="automatic-snapshots-settings__schedule">
                      <span>{{ row.scheduleText }}</span>
                    </div>
                    <div
                      v-if="row.nextRunText"
                      class="automatic-snapshots-settings__muted"
                    >
                      {{ row.nextRunText }}
                    </div>
                  </td>
                  <td class="automatic-snapshots-settings__menu-column">
                    <ButtonIcon
                      v-if="row.editable"
                      :ref="(el) => setMenuButton(row.application_id, el)"
                      icon="iconoir-more-horiz"
                      type="secondary"
                      :aria-label="
                        $t('automaticSnapshotsSettings.rowActions', {
                          name: row.application_name,
                        })
                      "
                      @click="openRowMenu(row)"
                    ></ButtonIcon>
                  </td>
                </tr>
                <tr
                  v-if="row.blockedWarning"
                  class="automatic-snapshots-settings__warning-row"
                >
                  <td></td>
                  <td colspan="4">
                    <Alert
                      type="error"
                      appearance="compact"
                      class="automatic-snapshots-settings__row-warning"
                    >
                      {{ row.blockedWarning }}
                    </Alert>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div v-else class="automatic-snapshots-settings__empty">
          {{
            rows.length === 0
              ? $t('automaticSnapshotsSettings.noApplications')
              : $t('automaticSnapshotsSettings.noSearchResults')
          }}
        </div>
        <div
          v-if="totalPages > 1"
          class="automatic-snapshots-settings__pagination"
        >
          <Paginator
            :page="page"
            :total-pages="totalPages"
            @change-page="page = $event"
          ></Paginator>
        </div>
      </section>
    </template>

    <Context ref="rowMenu" overflow-scroll max-height-if-outside-viewport>
      <ul v-if="menuRow" class="context__menu">
        <li class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="editRow(menuRow)">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{
              menuRow.state === 'workspace_default'
                ? $t('automaticSnapshotsSettings.customise')
                : $t('automaticSnapshots.edit')
            }}
          </a>
        </li>
        <li v-if="menuRow.scheduled" class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click.prevent="turnOffRow(menuRow)"
          >
            <i class="context__menu-item-icon iconoir-pause"></i>
            {{ $t('automaticSnapshotsSettings.turnOff') }}
          </a>
        </li>
        <li v-else-if="menuRow.state === 'off'" class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click.prevent="turnOnRow(menuRow)"
          >
            <i class="context__menu-item-icon iconoir-play"></i>
            {{ $t('automaticSnapshotsSettings.turnOn') }}
          </a>
        </li>
        <li
          v-if="menuRow.state !== 'workspace_default'"
          class="context__menu-item"
        >
          <a class="context__menu-item-link" @click.prevent="resetRow(menuRow)">
            <i class="context__menu-item-icon iconoir-undo"></i>
            {{ resetLabel }}
          </a>
        </li>
      </ul>
    </Context>

    <AutomaticSnapshotScheduleModal
      v-if="data"
      ref="scheduleModal"
      :title="modalTitle"
      :min-interval-minutes="data.min_interval_minutes"
      :saving="saving"
      @submitted="saveSchedule"
    ></AutomaticSnapshotScheduleModal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'
import Paginator from '@baserow/modules/core/components/Paginator'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { FF_AUTOMATIC_SNAPSHOTS } from '@baserow/modules/core/plugins/featureFlags'
import AutomaticSnapshotsService from '@baserow_enterprise/services/automaticSnapshots'
import AutomaticSnapshotScheduleModal from '@baserow_enterprise/components/automaticSnapshots/AutomaticSnapshotScheduleModal'
import {
  LOCAL_TIME_INTERVALS,
  describeSchedule,
  formatRunTime,
  getNewScheduleValues,
  getScheduleBlockedWarning,
  getScheduleValues,
} from '@baserow_enterprise/utils/automaticSnapshots'

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  /**
   * The snapshot settings of the workspace, as the core settings load them, with
   * the max snapshots and protected snapshots of every application. `null` while loading.
   */
  snapshotSettings: {
    type: Object,
    required: false,
    default: null,
  },
})

const {
  $client,
  $featureFlagIsEnabled,
  $hasFeature,
  $hasPermission,
  $registry,
  $store,
} = useNuxtApp()

// Automatic snapshots are hidden until the feature flag is turned on.
const featureFlagEnabled = computed(() =>
  $featureFlagIsEnabled(FF_AUTOMATIC_SNAPSHOTS)
)
const { t } = useI18n()
const service = AutomaticSnapshotsService($client)

const hasFeature = computed(() =>
  $hasFeature(EnterpriseFeatures.AUTOMATIC_SNAPSHOTS, props.workspace.id)
)
const paidFeaturesModal = ref(null)
const loading = ref(false)
const loadFailed = ref(false)
const saving = ref(false)
const actionLoading = ref(false)
const data = ref(null)
const selectedIds = ref([])
const rowMenu = ref(null)
const menuRow = ref(null)
const menuButtons = {}
const scheduleModal = ref(null)
// What saving the schedule modal changes: the workspace default, one
// application, or the selected applications.
const formTarget = ref(null)

const workspaceDefault = computed(() => data.value?.workspace_default || null)
// Deleting an application's own schedule makes it follow the workspace default,
// or leaves it without a schedule when there is none.
const resetLabel = computed(() =>
  workspaceDefault.value
    ? t('automaticSnapshots.resetToWorkspace')
    : t('automaticSnapshots.remove')
)
const canRead = computed(() =>
  $hasPermission(
    'workspace.read_automatic_snapshot_schedule',
    props.workspace,
    props.workspace.id
  )
)
const canUpdateWorkspace = computed(() =>
  $hasPermission(
    'workspace.update_automatic_snapshot_schedule',
    props.workspace,
    props.workspace.id
  )
)

function describe(schedule) {
  return describeSchedule(schedule, t)
}

function showsTimezone(schedule) {
  return LOCAL_TIME_INTERVALS.includes(schedule.interval)
}

function formatNextRun(schedule) {
  return schedule?.next_run_at
    ? formatRunTime(schedule, schedule.next_run_at)
    : '—'
}

const coveredCount = computed(
  () => rows.value.filter((row) => row.state === 'workspace_default').length
)

const workspaceDefaultDetail = computed(() => {
  const schedule = workspaceDefault.value
  return [
    t('automaticSnapshots.nextRun', { date: formatNextRun(schedule) }),
    t('automaticSnapshotsSettings.covers', { count: coveredCount.value }),
  ].join(' · ')
})

function canUpdateApplication(applicationId) {
  const application = $store.getters['application/get'](applicationId) || {
    id: applicationId,
  }
  return $hasPermission(
    'application.update_automatic_snapshot_schedule',
    application,
    props.workspace.id
  )
}

// Few enough rows that the page fits in the Workspace Settings modal without
// scrolling it.
const PAGE_SIZE = 5
const search = ref('')
const page = ref(1)

// The applications come from the store, which holds every application the user
// can see and is kept up to date in real time. The API only sends the schedules.
const scheduleByApplicationId = computed(() =>
  Object.fromEntries(
    (data.value?.application_schedules || []).map((schedule) => [
      schedule.application_id,
      schedule,
    ])
  )
)

const snapshotSettingsByApplicationId = computed(() =>
  Object.fromEntries(
    (props.snapshotSettings?.applications || []).map((application) => [
      application.id,
      application,
    ])
  )
)

// Why scheduled runs can't snapshot the application, if they can't.
function getBlockedWarning(application) {
  const settings = props.snapshotSettings
  const snapshotSettings = snapshotSettingsByApplicationId.value[application.id]
  if (!settings || !snapshotSettings) {
    return ''
  }
  return (
    getScheduleBlockedWarning(
      {
        limit: settings.limit,
        maxSnapshots:
          snapshotSettings.max_snapshots ?? settings.default_max_snapshots,
        protectedCount: snapshotSettings.protected_count,
      },
      application.name,
      t,
      true
    ) || ''
  )
}

const rows = computed(() => {
  if (!data.value) {
    return []
  }
  const defaultSchedule = workspaceDefault.value
  const applications = [
    ...$store.getters['application/getAllOfWorkspace'](props.workspace),
  ].sort((a, b) => a.order - b.order || a.id - b.id)
  return applications.map((application) => {
    const schedule = scheduleByApplicationId.value[application.id] || null
    let state = 'workspace_default'
    if (schedule) {
      state = schedule.enabled ? 'own_schedule' : 'off'
    }
    // The schedule that creates the snapshots of this application, if any.
    let active = null
    if (state === 'own_schedule') {
      active = schedule
    } else if (state === 'workspace_default' && defaultSchedule?.enabled) {
      active = defaultSchedule
    }
    let badge
    if (state === 'own_schedule') {
      badge = { color: 'cyan', label: t('automaticSnapshots.badgeOwn') }
    } else if (state === 'off') {
      badge = { color: 'neutral', label: t('automaticSnapshots.badgeOff') }
    } else if (defaultSchedule?.enabled) {
      badge = {
        color: 'neutral',
        label: t('automaticSnapshots.badgeWorkspace'),
      }
    } else {
      // No workspace schedule applies, so nothing creates its snapshots.
      badge = {
        color: 'neutral',
        label: t('automaticSnapshotsSettings.badgeNotScheduled'),
      }
    }
    return {
      application_id: application.id,
      application_name: application.name,
      state,
      schedule,
      badge,
      // Whether a schedule creates the snapshots of this application.
      scheduled: active !== null,
      editable: canUpdateApplication(application.id),
      iconClass: $registry.get('application', application.type).getIconClass(),
      scheduleText: active ? describe(active) : '—',
      nextRunText: active
        ? t('automaticSnapshotsSettings.nextRun', {
            date: formatNextRun(active),
          })
        : '',
      blockedWarning: active ? getBlockedWarning(application) : '',
    }
  })
})

const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) {
    return rows.value
  }
  return rows.value.filter((row) =>
    row.application_name.toLowerCase().includes(query)
  )
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredRows.value.length / PAGE_SIZE))
)

const pagedRows = computed(() =>
  filteredRows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
)

// The selection is the visible page's, so it's cleared when the page or the
// search changes, and a page is never left past the last one.
watch(search, () => {
  page.value = 1
  selectedIds.value = []
})
watch(page, () => {
  selectedIds.value = []
})
// Applications can be removed while the page is open, for example by another user,
// so they're removed from the selection too.
watch(rows, (currentRows) => {
  const ids = new Set(currentRows.map((row) => row.application_id))
  if (selectedIds.value.some((id) => !ids.has(id))) {
    selectedIds.value = selectedIds.value.filter((id) => ids.has(id))
  }
})
watch(totalPages, (pages) => {
  if (page.value > pages) {
    page.value = pages
  }
})

const editableRows = computed(() =>
  pagedRows.value.filter((row) => row.editable)
)
const allSelected = computed(
  () =>
    editableRows.value.length > 0 &&
    editableRows.value.every((row) =>
      selectedIds.value.includes(row.application_id)
    )
)

function toggleAll() {
  selectedIds.value = allSelected.value
    ? []
    : editableRows.value.map((row) => row.application_id)
}

function toggleRow(row) {
  selectedIds.value = selectedIds.value.includes(row.application_id)
    ? selectedIds.value.filter((id) => id !== row.application_id)
    : [...selectedIds.value, row.application_id]
}

function setMenuButton(applicationId, el) {
  menuButtons[applicationId] = el
}

function openRowMenu(row) {
  menuRow.value = row
  rowMenu.value.toggle(
    menuButtons[row.application_id].$el,
    'bottom',
    'right',
    4
  )
}

const modalTitle = computed(() => {
  const target = formTarget.value
  if (!target) {
    return ''
  }
  if (target.kind === 'workspace') {
    return t('automaticSnapshotsSettings.workspaceSchedule')
  }
  if (target.kind === 'bulk') {
    return t('automaticSnapshotsSettings.bulkTitle', {
      count: target.applicationIds.length,
    })
  }
  return t('automaticSnapshots.modalTitle', {
    name: target.row.application_name,
  })
})

function newScheduleValues() {
  if (workspaceDefault.value) {
    return { ...getScheduleValues(workspaceDefault.value), enabled: true }
  }
  return getNewScheduleValues(
    data.value.min_interval_minutes,
    moment.tz.guess()
  )
}

function openWorkspaceForm() {
  formTarget.value = { kind: 'workspace' }
  scheduleModal.value.show(
    workspaceDefault.value
      ? getScheduleValues(workspaceDefault.value)
      : getNewScheduleValues(data.value.min_interval_minutes, moment.tz.guess())
  )
}

function openBulkForm() {
  formTarget.value = { kind: 'bulk', applicationIds: [...selectedIds.value] }
  scheduleModal.value.show(newScheduleValues())
}

function editRow(row) {
  rowMenu.value.hide()
  formTarget.value = { kind: 'application', row }
  scheduleModal.value.show(
    row.schedule ? getScheduleValues(row.schedule) : newScheduleValues()
  )
}

async function runAction(request) {
  actionLoading.value = true
  try {
    await request()
    await loadSchedules()
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    actionLoading.value = false
  }
}

function turnOffRow(row) {
  rowMenu.value.hide()
  return runAction(() =>
    row.schedule
      ? service.updateApplicationSchedule(row.application_id, {
          enabled: false,
        })
      : service.createApplicationSchedule(row.application_id, {
          ...newScheduleValues(),
          enabled: false,
        })
  )
}

function turnOnRow(row) {
  rowMenu.value.hide()
  return runAction(() =>
    service.updateApplicationSchedule(row.application_id, { enabled: true })
  )
}

function resetRow(row) {
  rowMenu.value.hide()
  return runAction(() => service.deleteApplicationSchedule(row.application_id))
}

function toggleWorkspaceDefault(enabled) {
  return runAction(() =>
    service.updateWorkspaceDefault(props.workspace.id, { enabled })
  )
}

function deleteWorkspaceDefault() {
  return runAction(() => service.deleteWorkspaceDefault(props.workspace.id))
}

function bulkReset() {
  const applicationIds = [...selectedIds.value]
  return runAction(async () => {
    await service.bulkUpdate(props.workspace.id, {
      application_ids: applicationIds,
      action: 'reset',
    })
    selectedIds.value = []
  })
}

async function saveSchedule(values) {
  const target = formTarget.value
  saving.value = true
  try {
    if (target.kind === 'workspace') {
      if (workspaceDefault.value) {
        await service.updateWorkspaceDefault(props.workspace.id, values)
      } else {
        await service.createWorkspaceDefault(props.workspace.id, values)
      }
    } else if (target.kind === 'bulk') {
      await service.bulkUpdate(props.workspace.id, {
        application_ids: target.applicationIds,
        action: 'apply',
        schedule: values,
      })
      selectedIds.value = []
    } else if (target.row.schedule) {
      await service.updateApplicationSchedule(target.row.application_id, values)
    } else {
      await service.createApplicationSchedule(target.row.application_id, {
        ...values,
        enabled: true,
      })
    }
    scheduleModal.value.hide()
    await loadSchedules()
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    saving.value = false
  }
}

async function loadSchedules() {
  const { data: response } = await service.getWorkspaceSchedules(
    props.workspace.id
  )
  data.value = response
}

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    await loadSchedules()
  } catch (error) {
    loadFailed.value = true
    notifyIf(error, 'application')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!featureFlagEnabled.value || !hasFeature.value || !canRead.value) {
    return
  }
  return load()
})
</script>
