<template>
  <section
    v-if="featureFlagEnabled && (!hasFeature || canRead)"
    class="automatic-snapshot-schedule"
    :class="{
      'automatic-snapshot-schedule--empty': hasFeature && isEmpty,
    }"
  >
    <div class="automatic-snapshot-schedule__main">
      <div
        class="automatic-snapshot-schedule__icon"
        :class="`automatic-snapshot-schedule__icon--${iconStyle}`"
      >
        <i :class="hasFeature ? 'iconoir-clock' : 'iconoir-lock'"></i>
      </div>
      <div class="automatic-snapshot-schedule__body">
        <div class="automatic-snapshot-schedule__head">
          <h2 class="automatic-snapshot-schedule__title">
            {{ $t('automaticSnapshots.title') }}
          </h2>
          <Badge v-if="!hasFeature" color="cyan" size="small" rounded>
            {{ $t('automaticSnapshots.enterpriseBadge') }}
          </Badge>
          <Badge v-else-if="stateBadge" :color="stateBadge.color" size="small">
            {{ stateBadge.label }}
          </Badge>
        </div>

        <template v-if="!hasFeature">
          <div class="automatic-snapshot-schedule__description">
            {{ $t('automaticSnapshots.upsell', { name: application.name }) }}
          </div>
          <div class="automatic-snapshot-schedule__inline-actions">
            <Button
              type="secondary"
              size="small"
              @click="paidFeaturesModal.show()"
              >{{ $t('automaticSnapshots.learnMore') }}</Button
            >
          </div>
        </template>

        <div v-else-if="loading" class="loading"></div>

        <template v-else-if="loadFailed">
          <div class="automatic-snapshot-schedule__description">
            {{ $t('automaticSnapshots.loadFailed') }}
          </div>
          <div class="automatic-snapshot-schedule__inline-actions">
            <Button type="secondary" size="small" @click="load">{{
              $t('action.retry')
            }}</Button>
          </div>
        </template>

        <template v-else-if="overview">
          <template v-if="activeSchedule">
            <div class="automatic-snapshot-schedule__schedule">
              {{ describe(activeSchedule) }}
              <span
                v-if="showsTimezone(activeSchedule)"
                class="automatic-snapshot-schedule__timezone"
                >· {{ activeSchedule.timezone }}</span
              >
            </div>
            <div class="automatic-snapshot-schedule__detail">
              {{ activeScheduleDetail }}
            </div>
          </template>
          <div v-else class="automatic-snapshot-schedule__description">
            {{ emptyDescription }}
          </div>
          <div
            v-if="isEmpty && canUpdate"
            class="automatic-snapshot-schedule__inline-actions"
          >
            <Button size="small" @click="openForm(true)">{{
              $t('automaticSnapshots.setUp')
            }}</Button>
          </div>
        </template>
      </div>
      <SwitchInput
        v-if="hasFeature && overview && !isEmpty && canUpdate"
        small
        role="switch"
        :tabindex="actionLoading ? -1 : 0"
        :aria-checked="switchedOn ? 'true' : 'false'"
        :aria-disabled="actionLoading ? 'true' : undefined"
        :value="switchedOn"
        :disabled="actionLoading"
        :aria-label="$t('automaticSnapshots.title')"
        @input="toggle"
        @keydown.enter.prevent="!actionLoading && toggle(!switchedOn)"
        @keydown.space.prevent="!actionLoading && toggle(!switchedOn)"
      ></SwitchInput>
    </div>

    <Alert
      v-if="hasFeature && activeSchedule && maxSnapshotsWarning"
      type="warning"
      class="automatic-snapshot-schedule__warning"
    >
      {{ maxSnapshotsWarning }}
    </Alert>

    <div
      v-if="hasFeature && ownSchedule && ownSchedule.last_error"
      class="automatic-snapshot-schedule__error"
    >
      <i class="iconoir-warning-circle"></i>
      <span>{{
        $t('automaticSnapshots.lastError', { error: ownSchedule.last_error })
      }}</span>
    </div>

    <div
      v-if="hasFeature && overview && !isEmpty && canUpdate"
      class="automatic-snapshot-schedule__footer"
    >
      <template v-if="overview.state === 'workspace_default'">
        <Button type="secondary" size="small" @click="openForm(true)">
          <span
            class="automatic-snapshot-schedule__customise"
            :title="
              $t('automaticSnapshots.customise', { name: application.name })
            "
            >{{
              $t('automaticSnapshots.customise', { name: application.name })
            }}</span
          >
        </Button>
        <span class="automatic-snapshot-schedule__footer-note">{{
          $t('automaticSnapshots.setByWorkspace')
        }}</span>
      </template>
      <template v-else>
        <Button type="secondary" size="small" @click="openForm(false)">{{
          $t('automaticSnapshots.edit')
        }}</Button>
        <ButtonText :loading="actionLoading" @click="reset">{{
          workspaceDefault
            ? $t('automaticSnapshots.resetToWorkspace')
            : $t('automaticSnapshots.remove')
        }}</ButtonText>
      </template>
    </div>

    <PaidFeaturesModal
      v-if="!hasFeature"
      ref="paidFeaturesModal"
      :workspace="application.workspace"
      initial-selected-type="automatic_snapshots"
    ></PaidFeaturesModal>

    <AutomaticSnapshotScheduleModal
      v-if="overview"
      ref="scheduleModal"
      :title="$t('automaticSnapshots.modalTitle', { name: application.name })"
      :min-interval-minutes="overview.min_interval_minutes"
      :saving="saving"
      @submitted="saveSchedule"
    ></AutomaticSnapshotScheduleModal>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'
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
  application: {
    type: Object,
    required: true,
  },
  /**
   * The snapshot usage of the application from the snapshots modal, `null` while
   * it's loading. It says whether scheduled runs can create anything.
   */
  snapshotUsage: {
    type: Object,
    required: false,
    default: null,
  },
})

const { $client, $featureFlagIsEnabled, $hasFeature, $hasPermission } =
  useNuxtApp()

// Automatic snapshots are hidden until the feature flag is turned on.
const featureFlagEnabled = computed(() =>
  $featureFlagIsEnabled(FF_AUTOMATIC_SNAPSHOTS)
)
const { t } = useI18n()

const loading = ref(false)
const loadFailed = ref(false)
const saving = ref(false)
const actionLoading = ref(false)
const overview = ref(null)
// Whether saving the schedule form creates the application's own schedule or
// updates it.
const formCreates = ref(false)
const paidFeaturesModal = ref(null)
const scheduleModal = ref(null)

const workspace = computed(() => props.application.workspace)
const hasFeature = computed(() =>
  $hasFeature(EnterpriseFeatures.AUTOMATIC_SNAPSHOTS, workspace.value.id)
)
const canRead = computed(() =>
  $hasPermission(
    'application.read_automatic_snapshot_schedule',
    props.application,
    workspace.value.id
  )
)
const canUpdate = computed(() =>
  $hasPermission(
    'application.update_automatic_snapshot_schedule',
    props.application,
    workspace.value.id
  )
)
const service = AutomaticSnapshotsService($client)

const ownSchedule = computed(() => overview.value?.schedule || null)
const workspaceDefault = computed(
  () => overview.value?.workspace_default || null
)
const followsEnabledDefault = computed(
  () =>
    overview.value?.state === 'workspace_default' &&
    workspaceDefault.value?.enabled
)
// Nothing applies: no schedule of its own and no enabled workspace default.
const isEmpty = computed(
  () =>
    overview.value?.state === 'workspace_default' &&
    !followsEnabledDefault.value
)
// The schedule that creates the snapshots of this application, if any.
const activeSchedule = computed(() => {
  if (overview.value?.state === 'own_schedule') {
    return ownSchedule.value
  }
  return followsEnabledDefault.value ? workspaceDefault.value : null
})
const switchedOn = computed(() => activeSchedule.value !== null)

// Why scheduled runs create nothing, when they can't: snapshots are turned off,
// the application has a max of 0, so runs skip it, or every snapshot it keeps is
// protected, so runs fail.
const maxSnapshotsWarning = computed(() => {
  const usage = props.snapshotUsage
  if (!usage) {
    return ''
  }
  return (
    getScheduleBlockedWarning(
      {
        limit: usage.limit,
        maxSnapshots: usage.effective_max_snapshots,
        protectedCount: usage.protected_count,
      },
      props.application.name,
      t
    ) || ''
  )
})

const stateBadge = computed(() => {
  if (!overview.value || isEmpty.value) {
    return null
  }
  switch (overview.value.state) {
    case 'own_schedule':
      return { color: 'cyan', label: t('automaticSnapshots.badgeOwn') }
    case 'off':
      return { color: 'neutral', label: t('automaticSnapshots.badgeOff') }
    default:
      return {
        color: 'neutral',
        label: t('automaticSnapshots.badgeWorkspace'),
      }
  }
})

const iconStyle = computed(() => {
  if (!hasFeature.value || overview.value?.state === 'off') {
    return 'neutral'
  }
  return 'blue'
})

const emptyDescription = computed(() =>
  overview.value?.state === 'off'
    ? t('automaticSnapshots.off', { name: props.application.name })
    : t('automaticSnapshots.none', { name: props.application.name })
)

function describe(schedule) {
  return describeSchedule(schedule, t)
}

function showsTimezone(schedule) {
  return LOCAL_TIME_INTERVALS.includes(schedule.interval)
}

const activeScheduleDetail = computed(() => {
  const schedule = activeSchedule.value
  if (!schedule.next_run_at) {
    return t('automaticSnapshots.upToMaxSnapshots')
  }
  const next = t('automaticSnapshots.nextRun', {
    date: formatRunTime(schedule, schedule.next_run_at),
  })
  return `${next} · ${t('automaticSnapshots.upToMaxSnapshots')}`
})

function newScheduleValues() {
  if (workspaceDefault.value) {
    return { ...getScheduleValues(workspaceDefault.value), enabled: true }
  }
  return getNewScheduleValues(
    overview.value.min_interval_minutes,
    moment.tz.guess()
  )
}

function openForm(creates) {
  formCreates.value = creates
  scheduleModal.value.show(
    creates ? newScheduleValues() : getScheduleValues(ownSchedule.value)
  )
}

async function runAction(request) {
  actionLoading.value = true
  try {
    await request()
    await loadOverview()
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    actionLoading.value = false
  }
}

function toggle(enabled) {
  const applicationId = props.application.id
  if (overview.value.state === 'workspace_default') {
    // Turning off an application that follows the workspace default gives it a
    // schedule of its own that is turned off.
    return runAction(() =>
      service.createApplicationSchedule(applicationId, {
        ...newScheduleValues(),
        enabled: false,
      })
    )
  }
  return runAction(() =>
    service.updateApplicationSchedule(applicationId, { enabled })
  )
}

function reset() {
  return runAction(() =>
    service.deleteApplicationSchedule(props.application.id)
  )
}

async function saveSchedule(values) {
  saving.value = true
  try {
    if (formCreates.value) {
      await service.createApplicationSchedule(props.application.id, {
        ...values,
        enabled: true,
      })
    } else {
      await service.updateApplicationSchedule(props.application.id, values)
    }
    scheduleModal.value.hide()
    await loadOverview()
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    saving.value = false
  }
}

async function loadOverview() {
  const { data } = await service.getApplicationOverview(props.application.id)
  overview.value = data
}

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    await loadOverview()
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
