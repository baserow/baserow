<template>
  <div class="node-error-handling-form">
    <div class="node-error-handling-form__title">
      {{ $t('nodeErrorHandlingForm.title') }}
    </div>
    <FormGroup
      :label="$t('nodeErrorHandlingForm.onFailureLabel')"
      :help-icon-tooltip="$t('nodeErrorHandlingForm.onFailureHelp')"
      small-label
      horizontal-narrow
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="onFailureSegments"
        :active-index="onFailureIndex"
        size="small"
        @update:active-index="selectOnFailure"
      />
    </FormGroup>
    <template v-if="retryEnabled">
      <FormGroup
        :label="$t('nodeErrorHandlingForm.retryOnLabel')"
        small-label
        horizontal-narrow
        required
        class="margin-bottom-2"
      >
        <div class="node-error-handling-form__reasons">
          <Checkbox
            :model-value="values.retry_on_failure"
            :disabled="readOnly"
            @update:model-value="update({ retry_on_failure: $event })"
          >
            {{ $t('nodeErrorHandlingForm.retryOnFailure') }}
          </Checkbox>
          <Checkbox
            :model-value="values.retry_on_condition"
            :disabled="readOnly"
            @update:model-value="update({ retry_on_condition: $event })"
          >
            {{ $t('nodeErrorHandlingForm.retryOnCondition') }}
          </Checkbox>
        </div>
      </FormGroup>
      <FormGroup
        v-if="values.retry_on_condition"
        :label="$t('nodeErrorHandlingForm.conditionLabel')"
        :help-icon-tooltip="$t('nodeErrorHandlingForm.conditionHelp')"
        small-label
        required
        class="margin-bottom-2"
      >
        <InjectedFormulaInput
          :model-value="values.retry_condition"
          :placeholder="$t('nodeErrorHandlingForm.conditionPlaceholder')"
          :disabled="readOnly"
          @update:model-value="update({ retry_condition: $event })"
        />
      </FormGroup>
      <FormGroup
        :label="$t('nodeErrorHandlingForm.retriesLabel')"
        :help-icon-tooltip="$t('nodeErrorHandlingForm.retriesHelp')"
        :error="v$.max_retries.$error"
        :error-message="v$.max_retries.$errors[0]?.$message"
        small-label
        horizontal-narrow
        required
        class="margin-bottom-2"
      >
        <FormInput
          :model-value="values.max_retries"
          :disabled="readOnly || !anyRetryReason"
          :error="v$.max_retries.$error"
          :to-value="toRetriesValue"
          :min="NODE_RETRIES.MIN"
          :max="NODE_RETRIES.MAX"
          type="number"
          @update:model-value="update({ max_retries: $event })"
        />
      </FormGroup>
    </template>
  </div>
</template>

<script setup>
import { computed, provide, reactive, watch } from 'vue'
import useVuelidate from '@vuelidate/core'
import {
  helpers,
  integer,
  maxValue,
  minValue,
  required,
} from '@vuelidate/validators'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import {
  DATA_PROVIDERS_ALLOWED_RETRY_CONDITION,
  NODE_ON_FAILURE,
  NODE_RETRIES,
} from '@baserow/modules/automation/enums'

/**
 * The "Error handling" section of the node side panel: what happens when an
 * attempt of the node fails. The values are kept locally and only the changed
 * keys are emitted through `values-changed`, so the side panel can diff and
 * debounce them the way it does for the node label.
 */
const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  readOnly: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['values-changed'])

const { $i18n } = useNuxtApp()

// The side panel provides the data providers its service form may use. The
// retry condition runs against the node's own result, so this subtree also
// gets the `current_node` provider; the formula component itself still comes
// from the panel.
provide('dataProvidersAllowed', DATA_PROVIDERS_ALLOWED_RETRY_CONDITION)

// The node always carries the policy fields: the API serializer returns them
// for every node and the store keeps the API payload as is.
const policyValues = () => ({
  on_failure: props.node.on_failure,
  max_retries: props.node.max_retries,
  retry_on_failure: props.node.retry_on_failure,
  retry_on_condition: props.node.retry_on_condition,
  retry_condition: props.node.retry_condition,
})

const values = reactive(policyValues())

const rules = {
  max_retries: {
    required: helpers.withMessage($i18n.t('error.requiredField'), required),
    integer: helpers.withMessage($i18n.t('error.integerField'), integer),
    minValue: helpers.withMessage(
      $i18n.t('error.minValueField', { min: NODE_RETRIES.MIN }),
      minValue(NODE_RETRIES.MIN)
    ),
    maxValue: helpers.withMessage(
      $i18n.t('error.maxValueField', { max: NODE_RETRIES.MAX }),
      maxValue(NODE_RETRIES.MAX)
    ),
  },
}
const v$ = useVuelidate(rules, values, { $lazy: true })

// Re-seed when the node object changes: another node was selected, or realtime
// (an undo/redo, another user's edit) replaced this one in the store. The
// user's own edits mutate the node in place, so a pending local value is left
// alone.
watch(
  () => props.node,
  () => {
    Object.assign(values, policyValues())
    v$.value.$reset()
  }
)

const retryEnabled = computed(() => values.on_failure === NODE_ON_FAILURE.RETRY)

const anyRetryReason = computed(
  () => values.retry_on_failure || values.retry_on_condition
)

const onFailureSegments = computed(() => [
  {
    value: NODE_ON_FAILURE.STOP,
    label: $i18n.t('nodeErrorHandlingForm.stop'),
  },
  {
    value: NODE_ON_FAILURE.RETRY,
    label: $i18n.t('nodeErrorHandlingForm.retry'),
  },
])

const onFailureIndex = computed(() =>
  onFailureSegments.value.findIndex(
    (segment) => segment.value === values.on_failure
  )
)

const selectOnFailure = (index) => {
  update({ on_failure: onFailureSegments.value[index].value })
}

// An emptied number input would otherwise parse to NaN, which the `required`
// validator accepts; `null` turns it into a plain "required" error instead.
const toRetriesValue = (value) => (value === '' ? null : parseInt(value, 10))

/**
 * Applies a change locally and emits only the changed keys. The retries count
 * is validated first and held back while out of range, so the other controls
 * keep working while the input shows its error. The segment control has no
 * disabled state of its own, so read-only mode is enforced here as well as by
 * the read-only form styles.
 */
const update = (changes) => {
  if (props.readOnly) {
    return
  }
  Object.assign(values, changes)
  if ('max_retries' in changes) {
    v$.value.max_retries.$touch()
    if (v$.value.max_retries.$invalid) {
      return
    }
  }
  emit('values-changed', changes)
}
</script>
