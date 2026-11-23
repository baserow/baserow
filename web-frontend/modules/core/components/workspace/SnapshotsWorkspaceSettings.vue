<template>
  <div class="snapshots-workspace-settings">
    <header class="snapshots-workspace-settings__header">
      <h2 class="snapshots-workspace-settings__title">
        {{ $t('snapshotsWorkspaceSettings.title') }}
      </h2>
      <p class="snapshots-workspace-settings__intro">
        {{ $t('snapshotsWorkspaceSettings.intro') }}
      </p>
    </header>

    <Alert v-if="!canRead" type="info">
      {{ $t('snapshotsWorkspaceSettings.adminsOnly') }}
    </Alert>

    <div v-else-if="loading" class="loading"></div>

    <template v-else-if="data">
      <section class="snapshots-workspace-settings__card">
        <div class="snapshots-workspace-settings__usage-head">
          <span class="snapshots-workspace-settings__card-title">{{
            $t('snapshotsWorkspaceSettings.allowance')
          }}</span>
          <span class="snapshots-workspace-settings__muted">{{
            usageText
          }}</span>
        </div>
        <div v-if="data.limit" class="snapshots-workspace-settings__usage-bar">
          <div
            class="snapshots-workspace-settings__usage-fill"
            :class="{
              'snapshots-workspace-settings__usage-fill--over':
                data.over_allowance,
            }"
            :style="{ width: `${usedPercentage}%` }"
          ></div>
        </div>
        <div class="snapshots-workspace-settings__muted">
          {{
            $t('snapshotsWorkspaceSettings.held', {
              count: data.snapshot_count,
            })
          }}
        </div>
        <div
          v-if="data.over_allowance"
          class="snapshots-workspace-settings__warning"
        >
          <i class="iconoir-warning-circle"></i>
          {{ $t('snapshotsWorkspaceSettings.overAllowance') }}
        </div>
      </section>

      <section
        v-if="data.limit !== 0"
        class="snapshots-workspace-settings__card"
      >
        <div class="snapshots-workspace-settings__max-snapshots">
          <div class="snapshots-workspace-settings__max-snapshots-body">
            <div class="snapshots-workspace-settings__card-title">
              {{ $t('snapshotsWorkspaceSettings.defaultMaxSnapshots') }}
            </div>
            <div class="snapshots-workspace-settings__muted">
              {{
                $t(
                  'snapshotsWorkspaceSettings.defaultMaxSnapshotsDescription',
                  {
                    count: followers.length,
                  }
                )
              }}
            </div>
          </div>
          <template v-if="!editing">
            <span class="snapshots-workspace-settings__max-snapshots-value">{{
              data.default_max_snapshots
            }}</span>
            <Button
              v-if="canUpdate"
              type="secondary"
              size="small"
              @click="edit"
              >{{ $t('maxSnapshots.change') }}</Button
            >
          </template>
        </div>

        <form
          v-if="editing"
          class="snapshots-workspace-settings__form"
          @submit.prevent="save()"
        >
          <FormInput
            v-model="draft"
            class="snapshots-workspace-settings__input"
            type="number"
            size="small"
            :min="0"
            :error="error !== null"
            :aria-label="$t('snapshotsWorkspaceSettings.defaultMaxSnapshots')"
          ></FormInput>
          <Button
            size="small"
            :loading="saving"
            :disabled="saving || error !== null || confirmingCount > 0"
            >{{ $t('maxSnapshots.save') }}</Button
          >
          <ButtonText button-type="button" :disabled="saving" @click="cancel">{{
            $t('action.cancel')
          }}</ButtonText>
        </form>
        <div
          v-if="editing && error"
          class="snapshots-workspace-settings__error"
        >
          {{ $t(error, errorParams) }}
        </div>
        <Alert
          v-else-if="overAllowance"
          type="warning"
          class="snapshots-workspace-settings__max-snapshots-warning"
        >
          {{
            $t('maxSnapshots.overAllowance', {
              used: newUsed(parseDraft()),
              limit: data.limit,
            })
          }}
        </Alert>
        <div
          v-if="confirmingCount > 0"
          class="snapshots-workspace-settings__confirm"
        >
          <span>{{
            $t('maxSnapshots.confirmDelete', {
              maxSnapshots: parseDraft(),
              count: confirmingCount,
            })
          }}</span>
          <Button
            type="secondary"
            size="small"
            button-type="button"
            :disabled="saving"
            @click="confirmingCount = 0"
            >{{ $t('action.cancel') }}</Button
          >
          <Button
            type="danger"
            size="small"
            :loading="saving"
            :disabled="saving"
            @click="save(true)"
            >{{ $t('maxSnapshots.deleteAndSave') }}</Button
          >
        </div>
      </section>

      <section
        v-if="rows.length > 0"
        class="snapshots-workspace-settings__applications"
      >
        <h3 class="snapshots-workspace-settings__card-title">
          {{ $t('snapshotsWorkspaceSettings.applications') }}
        </h3>
        <div class="snapshots-workspace-settings__table-scroll">
          <table class="snapshots-workspace-settings__table">
            <thead>
              <tr>
                <th>
                  {{ $t('snapshotsWorkspaceSettings.columnApplication') }}
                </th>
                <th class="snapshots-workspace-settings__number">
                  {{ $t('snapshotsWorkspaceSettings.columnMaxSnapshots') }}
                </th>
                <th class="snapshots-workspace-settings__number">
                  {{ $t('snapshotsWorkspaceSettings.columnSnapshots') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.id">
                <td>
                  <div class="snapshots-workspace-settings__application">
                    <i :class="row.iconClass"></i>
                    <span
                      class="snapshots-workspace-settings__application-name"
                      :title="row.name"
                      >{{ row.name }}</span
                    >
                  </div>
                </td>
                <td class="snapshots-workspace-settings__number">
                  {{ row.maxSnapshotsText }}
                </td>
                <td class="snapshots-workspace-settings__number">
                  {{ row.snapshotsText }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <Alert v-else type="error">
      {{ $t('snapshotsWorkspaceSettings.loadFailed') }}
    </Alert>

    <!-- Plugin sections load their own data, so they're shown even when the
    settings above couldn't be loaded. `snapshot-settings` is then `null`. -->
    <template v-if="canRead && !loading">
      <component
        :is="component"
        v-for="(component, index) in pluginComponents"
        :key="index"
        :workspace="workspace"
        :snapshot-settings="data"
      ></component>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  countSnapshotsDeletedByMaxSnapshots,
  getSnapshotsDeletedByMaxSnapshotsError,
  goesOverSnapshotAllowance,
  validateMaxSnapshots,
} from '@baserow/modules/core/utils/snapshots'

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
})

const { $client, $hasPermission, $registry, $store } = useNuxtApp()
const { t } = useI18n()
const service = SnapshotsService($client)

// Until the settings are loaded, so the load error isn't shown before.
const loading = ref(true)
const data = ref(null)
const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const confirmingCount = ref(0)

const canRead = computed(() =>
  $hasPermission(
    'workspace.read_snapshot_settings',
    props.workspace,
    props.workspace.id
  )
)

const canUpdate = computed(() =>
  $hasPermission(
    'workspace.update_snapshot_settings',
    props.workspace,
    props.workspace.id
  )
)

const usageText = computed(() => {
  const { used, limit } = data.value
  if (limit === 0) {
    return t('snapshotsWorkspaceSettings.disabled')
  }
  if (limit === null) {
    return t('snapshotsWorkspaceSettings.usageWithoutLimit', { used })
  }
  return t('snapshotsWorkspaceSettings.usage', { used, limit })
})

const usedPercentage = computed(() => {
  const { used, limit } = data.value
  return Math.min(100, (used / limit) * 100)
})

// The applications that follow the workspace default max snapshots.
const followers = computed(() =>
  (data.value?.applications || []).filter(
    (application) => application.max_snapshots === null
  )
)

const rows = computed(() =>
  (data.value?.applications || []).map((application) => {
    const stored = $store.getters['application/get'](application.id)
    const type = stored ? $registry.get('application', stored.type) : null
    const maxSnapshots =
      application.max_snapshots === null
        ? data.value.default_max_snapshots
        : application.max_snapshots
    return {
      id: application.id,
      name: stored ? stored.name : `#${application.id}`,
      iconClass: type ? type.getIconClass() : 'iconoir-app-window',
      maxSnapshotsText:
        application.max_snapshots === null
          ? t('snapshotsWorkspaceSettings.maxSnapshotsDefault', {
              count: maxSnapshots,
            })
          : String(maxSnapshots),
      snapshotsText:
        application.protected_count > 0
          ? t('snapshotsWorkspaceSettings.snapshotsProtected', {
              count: application.snapshot_count,
              protected: application.protected_count,
            })
          : String(application.snapshot_count),
    }
  })
)

const pluginComponents = computed(() =>
  Object.values($registry.getAll('plugin')).flatMap((plugin) =>
    plugin.getWorkspaceSnapshotSettingsComponents(props.workspace)
  )
)

function parseDraft() {
  const value = String(draft.value).trim()
  return /^\d+$/.test(value) ? parseInt(value, 10) : NaN
}

// How much of the allowance is reserved once the default max snapshots is `maxSnapshots`.
function newUsed(maxSnapshots) {
  const { used, default_max_snapshots: originalMaxSnapshots } = data.value
  return used + followers.value.length * (maxSnapshots - originalMaxSnapshots)
}

function validate(maxSnapshots) {
  const {
    used,
    limit,
    max_snapshots_limit: maxSnapshotsLimit,
    default_max_snapshots: originalMaxSnapshots,
    can_exceed_allowance: canExceedAllowance,
  } = data.value
  return validateMaxSnapshots({
    maxSnapshots,
    originalMaxSnapshots,
    used,
    newUsed: newUsed(maxSnapshots),
    limit,
    maxSnapshotsLimit,
    canExceedAllowance,
    protectedCount: Math.max(
      0,
      ...followers.value.map((application) => application.protected_count)
    ),
  })
}

const error = computed(() => (editing.value ? validate(parseDraft()) : null))

// Whether saving the default max snapshots takes the workspace over its allowance, when it
// can go over it.
const overAllowance = computed(
  () =>
    editing.value &&
    goesOverSnapshotAllowance({
      used: data.value.used,
      newUsed: newUsed(parseDraft()),
      limit: data.value.limit,
    })
)

const errorParams = computed(() => {
  const {
    used,
    limit,
    max_snapshots_limit: maxSnapshotsLimit,
    default_max_snapshots: originalMaxSnapshots,
  } = data.value
  const followerCount = Math.max(1, followers.value.length)
  return {
    count: {
      'maxSnapshots.errorBelowProtected': Math.max(
        0,
        ...followers.value.map((application) => application.protected_count)
      ),
      'maxSnapshots.errorAboveMaximum': maxSnapshotsLimit,
      'maxSnapshots.errorExceedsAllowance':
        limit === null
          ? null
          : Math.max(
              originalMaxSnapshots,
              originalMaxSnapshots + Math.floor((limit - used) / followerCount)
            ),
    }[error.value],
  }
})

watch(draft, () => {
  confirmingCount.value = 0
})

function edit() {
  draft.value = String(data.value.default_max_snapshots)
  confirmingCount.value = 0
  editing.value = true
}

function cancel() {
  editing.value = false
  confirmingCount.value = 0
}

async function save(deleteSnapshots = false) {
  const maxSnapshots = parseDraft()
  if (validate(maxSnapshots) !== null) {
    return
  }
  const toDelete = countSnapshotsDeletedByMaxSnapshots(
    followers.value.map((application) => ({
      snapshotCount: application.snapshot_count,
      protectedCount: application.protected_count,
    })),
    maxSnapshots
  )
  if (toDelete > 0 && !deleteSnapshots) {
    confirmingCount.value = toDelete
    return
  }

  saving.value = true
  try {
    const { data: response } = await service.updateWorkspaceDefaultMaxSnapshots(
      props.workspace.id,
      maxSnapshots,
      deleteSnapshots
    )
    data.value = response
    editing.value = false
    confirmingCount.value = 0
  } catch (error) {
    const count = getSnapshotsDeletedByMaxSnapshotsError(error)
    if (count !== null) {
      // The settings were out of date, so the deletion wasn't predicted. They're
      // loaded again and the deletion is confirmed like any other.
      confirmingCount.value = count
      loadSettings().catch((loadError) => notifyIf(loadError, 'application'))
    } else {
      notifyIf(error, 'application')
    }
  } finally {
    saving.value = false
  }
}

async function loadSettings() {
  const { data: response } = await service.getWorkspaceSettings(
    props.workspace.id
  )
  data.value = response
}

onMounted(async () => {
  if (!canRead.value) {
    return
  }
  loading.value = true
  try {
    await loadSettings()
  } catch (error) {
    notifyIf(error, 'application')
  } finally {
    loading.value = false
  }
})
</script>
