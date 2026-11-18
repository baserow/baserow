<template>
  <section class="snapshot-keep">
    <div class="snapshot-keep__main">
      <div class="snapshot-keep__body">
        <div class="snapshot-keep__title">{{ $t('snapshotKeep.title') }}</div>
        <div class="snapshot-keep__description">
          {{ description }}
        </div>
      </div>
      <template v-if="!editing">
        <span class="snapshot-keep__value">{{ usage.effective_keep }}</span>
        <Button
          v-if="canUpdate"
          type="secondary"
          size="small"
          @click="edit()"
          >{{ $t('snapshotKeep.change') }}</Button
        >
      </template>
    </div>

    <form v-if="editing" class="snapshot-keep__form" @submit.prevent="save()">
      <FormInput
        ref="input"
        v-model="draft"
        class="snapshot-keep__input"
        type="number"
        size="small"
        :min="0"
        :error="error !== null"
        :aria-label="$t('snapshotKeep.title')"
      ></FormInput>
      <span v-if="highestKeep !== null" class="snapshot-keep__hint">{{
        $t('snapshotKeep.upTo', { count: highestKeep })
      }}</span>
      <Button
        size="small"
        :loading="saving"
        :disabled="saving || error !== null || confirmingCount > 0"
        >{{ $t('snapshotKeep.save') }}</Button
      >
      <ButtonText button-type="button" :disabled="saving" @click="cancel()">{{
        $t('action.cancel')
      }}</ButtonText>
      <ButtonText
        v-if="usage.keep !== null"
        button-type="button"
        :disabled="saving"
        @click="save(null)"
        >{{
          $t('snapshotKeep.useDefault', { count: usage.default_keep })
        }}</ButtonText
      >
    </form>

    <div v-if="editing && error" class="snapshot-keep__error">
      {{ $t(error, errorParams) }}
    </div>
    <Alert
      v-else-if="overAllowance"
      type="warning"
      class="snapshot-keep__warning"
    >
      {{
        $t('snapshotKeep.overAllowance', {
          used: newUsed(parseDraft()),
          limit: usage.limit,
        })
      }}
    </Alert>

    <div v-if="confirmingCount > 0" class="snapshot-keep__confirm">
      <span>{{
        $t('snapshotKeep.confirmDelete', {
          keep: confirmingKeep ?? usage.default_keep,
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
        @click="save(confirmingKeep, true)"
        >{{ $t('snapshotKeep.deleteAndSave') }}</Button
      >
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  getSnapshotsDeletedByKeepError,
  getSnapshotsToDelete,
  goesOverSnapshotAllowance,
  validateSnapshotKeep,
} from '@baserow/modules/core/utils/snapshots'

const props = defineProps({
  application: {
    type: Object,
    required: true,
  },
  /**
   * The snapshot usage of the application, as the usage endpoint returns it.
   */
  usage: {
    type: Object,
    required: true,
  },
  /**
   * The restorable snapshots of the application.
   */
  snapshots: {
    type: Array,
    required: true,
  },
  canUpdate: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['updated', 'stale'])

const { $client } = useNuxtApp()
const { t } = useI18n()

const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const input = ref(null)
// When lowering the keep deletes snapshots, the keep and how many are deleted,
// until the deletion is confirmed.
const confirmingKeep = ref(null)
const confirmingCount = ref(0)

const description = computed(() => {
  const count = props.usage.effective_keep
  if (count === 0) {
    return t('snapshotKeep.descriptionNone')
  }
  return props.usage.keep === null
    ? t('snapshotKeep.descriptionDefault', { count })
    : t('snapshotKeep.descriptionOwn', { count })
})

// The highest keep the application can get: what's left of the allowance on top of
// its current keep, unless the workspace can go over it, and the maximum keep.
// `null` when there's no limit.
const highestKeep = computed(() => {
  const {
    limit,
    used,
    effective_keep: effectiveKeep,
    max_keep: maxKeep,
    can_exceed_allowance: canExceedAllowance,
  } = props.usage
  const candidates = []
  if (limit !== null && !canExceedAllowance) {
    candidates.push(Math.max(effectiveKeep, limit - used + effectiveKeep))
  }
  if (maxKeep !== null) {
    candidates.push(Math.max(effectiveKeep, maxKeep))
  }
  return candidates.length > 0 ? Math.min(...candidates) : null
})

function parseDraft() {
  const value = String(draft.value).trim()
  return /^\d+$/.test(value) ? parseInt(value, 10) : NaN
}

// How much of the allowance is reserved once the keep is changed to `keep`.
function newUsed(keep) {
  const effectiveKeep = keep === null ? props.usage.default_keep : keep
  return props.usage.used - props.usage.effective_keep + effectiveKeep
}

function validate(keep) {
  return validateSnapshotKeep({
    keep: keep === null ? props.usage.default_keep : keep,
    originalKeep: props.usage.effective_keep,
    used: props.usage.used,
    newUsed: newUsed(keep),
    limit: props.usage.limit,
    maxKeep: props.usage.max_keep,
    protectedCount: props.usage.protected_count,
    canExceedAllowance: props.usage.can_exceed_allowance,
  })
}

const error = computed(() => (editing.value ? validate(parseDraft()) : null))

// Whether saving the keep takes the workspace over its allowance, when it can go
// over it.
const overAllowance = computed(
  () =>
    editing.value &&
    goesOverSnapshotAllowance({
      used: props.usage.used,
      newUsed: newUsed(parseDraft()),
      limit: props.usage.limit,
    })
)

const errorParams = computed(() => {
  const { limit, used, effective_keep: effectiveKeep } = props.usage
  const count = {
    'snapshotKeep.errorBelowProtected': props.usage.protected_count,
    'snapshotKeep.errorAboveMaximum': props.usage.max_keep,
    'snapshotKeep.errorExceedsAllowance':
      limit === null
        ? null
        : Math.max(effectiveKeep, limit - used + effectiveKeep),
  }[error.value]
  return { count }
})

watch(draft, () => {
  confirmingCount.value = 0
})

/**
 * Opens the form to change the keep.
 *
 * @param {number|null} suggested The keep to fill in, defaults to the current one.
 */
async function edit(suggested = null) {
  draft.value = String(suggested ?? props.usage.effective_keep)
  confirmingCount.value = 0
  editing.value = true
  await nextTick()
  input.value?.focus?.()
}

function cancel() {
  editing.value = false
  confirmingCount.value = 0
}

async function save(keep = parseDraft(), deleteSnapshots = false) {
  if (validate(keep) !== null) {
    return
  }
  const effectiveKeep = keep === null ? props.usage.default_keep : keep
  const toDelete = getSnapshotsToDelete(props.snapshots, effectiveKeep).length
  if (toDelete > 0 && !deleteSnapshots) {
    confirmingKeep.value = keep
    confirmingCount.value = toDelete
    return
  }

  saving.value = true
  try {
    const { data } = await SnapshotsService($client).updateKeep(
      props.application.id,
      keep,
      deleteSnapshots
    )
    editing.value = false
    confirmingCount.value = 0
    emit('updated', data)
  } catch (error) {
    const count = getSnapshotsDeletedByKeepError(error)
    if (count !== null) {
      // The list was out of date, so the deletion wasn't predicted. The list is
      // loaded again and the deletion is confirmed like any other.
      confirmingKeep.value = keep
      confirmingCount.value = count
      emit('stale')
    } else {
      notifyIf(error, 'application')
    }
  } finally {
    saving.value = false
  }
}

defineExpose({ edit })
</script>
