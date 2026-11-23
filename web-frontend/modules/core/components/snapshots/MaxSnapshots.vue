<template>
  <section class="max-snapshots">
    <div class="max-snapshots__main">
      <div class="max-snapshots__body">
        <div class="max-snapshots__title">{{ $t('maxSnapshots.title') }}</div>
        <div class="max-snapshots__description">
          {{ description }}
        </div>
        <div
          v-if="usage.max_snapshots === null"
          class="max-snapshots__source max-snapshots__source--inherited"
        >
          {{
            $t('maxSnapshots.sourceWorkspace', {
              count: usage.default_max_snapshots,
            })
          }}
        </div>
      </div>
      <template v-if="!editing">
        <span class="max-snapshots__value">{{
          usage.effective_max_snapshots
        }}</span>
        <Button
          v-if="canUpdate"
          type="secondary"
          size="small"
          @click="edit()"
          >{{ $t('maxSnapshots.change') }}</Button
        >
      </template>
    </div>

    <form v-if="editing" class="max-snapshots__form" @submit.prevent="save()">
      <FormInput
        ref="input"
        v-model="draft"
        class="max-snapshots__input"
        type="number"
        size="small"
        :min="0"
        :error="error !== null"
        :aria-label="$t('maxSnapshots.title')"
      ></FormInput>
      <span v-if="highestMaxSnapshots !== null" class="max-snapshots__hint">{{
        $t('maxSnapshots.upTo', { count: highestMaxSnapshots })
      }}</span>
      <Button
        size="small"
        :loading="saving"
        :disabled="saving || error !== null || confirmingCount > 0"
        >{{ $t('maxSnapshots.save') }}</Button
      >
      <ButtonText button-type="button" :disabled="saving" @click="cancel()">{{
        $t('action.cancel')
      }}</ButtonText>
      <ButtonText
        v-if="usage.max_snapshots !== null"
        button-type="button"
        :disabled="saving"
        @click="save(null)"
        >{{
          $t('maxSnapshots.useDefault', { count: usage.default_max_snapshots })
        }}</ButtonText
      >
    </form>

    <div v-if="editing && shownError" class="max-snapshots__error">
      {{ $t(shownError, errorParams) }}
    </div>
    <Alert
      v-else-if="overAllowance"
      type="warning"
      class="max-snapshots__warning"
    >
      {{
        $t('maxSnapshots.overAllowance', {
          used: newUsed(parseDraft()),
          limit: usage.limit,
        })
      }}
    </Alert>

    <div v-if="confirmingCount > 0" class="max-snapshots__confirm">
      <span>{{
        $t('maxSnapshots.confirmDelete', {
          maxSnapshots: confirmingMaxSnapshots ?? usage.default_max_snapshots,
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
        @click="save(confirmingMaxSnapshots, true)"
        >{{ $t('maxSnapshots.deleteAndSave') }}</Button
      >
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  getSnapshotsDeletedByMaxSnapshotsError,
  getSnapshotsToDelete,
  goesOverSnapshotAllowance,
  validateMaxSnapshots,
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
// When lowering the max snapshots deletes snapshots, the max snapshots and how many are deleted,
// until the deletion is confirmed.
const confirmingMaxSnapshots = ref(null)
const confirmingCount = ref(0)

const description = computed(() => {
  const count = props.usage.effective_max_snapshots
  if (count === 0) {
    return t('maxSnapshots.descriptionNone')
  }
  return props.usage.max_snapshots === null
    ? t('maxSnapshots.descriptionDefault', { count })
    : t('maxSnapshots.descriptionOwn', { count })
})

// The highest max snapshots the application can get: what's left of the allowance on top of
// its current max snapshots, unless the workspace can go over it, and the max snapshots limit.
// `null` when there's no limit.
const highestMaxSnapshots = computed(() => {
  const {
    limit,
    used,
    effective_max_snapshots: effectiveMaxSnapshots,
    max_snapshots_limit: maxSnapshotsLimit,
    can_exceed_allowance: canExceedAllowance,
  } = props.usage
  const candidates = []
  if (limit !== null && !canExceedAllowance) {
    candidates.push(
      Math.max(effectiveMaxSnapshots, limit - used + effectiveMaxSnapshots)
    )
  }
  if (maxSnapshotsLimit !== null) {
    candidates.push(Math.max(effectiveMaxSnapshots, maxSnapshotsLimit))
  }
  return candidates.length > 0 ? Math.min(...candidates) : null
})

function parseDraft() {
  const value = String(draft.value).trim()
  return /^\d+$/.test(value) ? parseInt(value, 10) : NaN
}

// How much of the allowance is reserved once the max snapshots is changed to `maxSnapshots`.
function newUsed(maxSnapshots) {
  const effectiveMaxSnapshots =
    maxSnapshots === null ? props.usage.default_max_snapshots : maxSnapshots
  return (
    props.usage.used -
    props.usage.effective_max_snapshots +
    effectiveMaxSnapshots
  )
}

function validate(maxSnapshots) {
  return validateMaxSnapshots({
    maxSnapshots:
      maxSnapshots === null ? props.usage.default_max_snapshots : maxSnapshots,
    originalMaxSnapshots: props.usage.effective_max_snapshots,
    used: props.usage.used,
    newUsed: newUsed(maxSnapshots),
    limit: props.usage.limit,
    maxSnapshotsLimit: props.usage.max_snapshots_limit,
    protectedCount: props.usage.protected_count,
    canExceedAllowance: props.usage.can_exceed_allowance,
  })
}

const error = computed(() => (editing.value ? validate(parseDraft()) : null))
// Why the workspace default can't be used, once "Use default" was clicked.
const defaultError = ref(null)
const shownError = computed(() => error.value ?? defaultError.value)

// Whether saving the max snapshots takes the workspace over its allowance, when it can go
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
  const {
    limit,
    used,
    effective_max_snapshots: effectiveMaxSnapshots,
  } = props.usage
  const count = {
    'maxSnapshots.errorBelowProtected': props.usage.protected_count,
    'maxSnapshots.errorAboveMaximum': props.usage.max_snapshots_limit,
    'maxSnapshots.errorExceedsAllowance':
      limit === null
        ? null
        : Math.max(effectiveMaxSnapshots, limit - used + effectiveMaxSnapshots),
  }[shownError.value]
  return { count }
})

watch(draft, () => {
  confirmingCount.value = 0
  defaultError.value = null
})

/**
 * Opens the form to change the max snapshots.
 *
 * @param {number|null} suggested The max snapshots to fill in, defaults to the current one.
 */
async function edit(suggested = null) {
  draft.value = String(suggested ?? props.usage.effective_max_snapshots)
  confirmingCount.value = 0
  defaultError.value = null
  editing.value = true
  await nextTick()
  input.value?.focus?.()
}

function cancel() {
  editing.value = false
  confirmingCount.value = 0
  defaultError.value = null
}

async function save(maxSnapshots = parseDraft(), deleteSnapshots = false) {
  const validationError = validate(maxSnapshots)
  if (validationError !== null) {
    if (maxSnapshots === null) {
      defaultError.value = validationError
    }
    return
  }
  const effectiveMaxSnapshots =
    maxSnapshots === null ? props.usage.default_max_snapshots : maxSnapshots
  const toDelete = getSnapshotsToDelete(
    props.snapshots,
    effectiveMaxSnapshots
  ).length
  if (toDelete > 0 && !deleteSnapshots) {
    confirmingMaxSnapshots.value = maxSnapshots
    confirmingCount.value = toDelete
    return
  }

  saving.value = true
  try {
    const { data } = await SnapshotsService($client).updateMaxSnapshots(
      props.application.id,
      maxSnapshots,
      deleteSnapshots
    )
    editing.value = false
    confirmingCount.value = 0
    emit('updated', data)
  } catch (error) {
    const count = getSnapshotsDeletedByMaxSnapshotsError(error)
    if (count !== null) {
      // The list was out of date, so the deletion wasn't predicted. The list is
      // loaded again and the deletion is confirmed like any other.
      confirmingMaxSnapshots.value = maxSnapshots
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
