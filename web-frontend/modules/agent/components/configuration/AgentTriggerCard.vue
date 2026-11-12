<template>
  <article class="agent-trigger-card" :aria-busy="saving">
    <header class="agent-trigger-card__header">
      <div class="agent-trigger-card__title">
        <button
          v-tooltip="typeName"
          type="button"
          class="agent-trigger-card__type"
          :disabled="!editable"
          aria-haspopup="menu"
          :aria-label="
            editable
              ? $t('agent.triggerChangeType', { type: typeName })
              : typeName
          "
          @click="typePicker.toggle($event.currentTarget)"
        >
          <Icon
            :icon="serviceType?.icon || 'iconoir-flash'"
            class="agent-trigger-card__icon"
            aria-hidden="true"
          />
          <i
            v-if="editable"
            class="agent-trigger-card__chevron iconoir-nav-arrow-down"
            aria-hidden="true"
          />
        </button>
        <div class="agent-trigger-card__name" @click="startRename">
          <Editable
            ref="nameEditable"
            class="agent-trigger-card__name-text"
            :value="shownName"
            @editing="renaming = $event"
            @change="rename"
          />
        </div>
        <button
          v-if="editable && !renaming"
          type="button"
          class="agent-trigger-card__rename"
          :aria-label="$t('agent.renameTrigger')"
          @click="startRename"
        >
          <i class="iconoir-edit-pencil" aria-hidden="true" />
        </button>
        <Icon
          v-if="configurationError"
          v-tooltip="configurationError"
          class="agent-trigger-card__status"
          icon="iconoir-warning-circle"
          type="error"
          size="small"
          role="img"
          :aria-label="configurationError"
        />
      </div>
      <span
        v-if="saving"
        class="agent-trigger-card__saving"
        role="status"
        :aria-label="$t('agent.saving')"
      />
      <SwitchInput
        class="agent-trigger-card__switch"
        small
        role="switch"
        :tabindex="editable ? 0 : -1"
        :aria-label="$t('agent.triggerEnabled')"
        :aria-checked="trigger.enabled"
        :aria-disabled="!editable"
        :model-value="trigger.enabled"
        :disabled="!editable"
        @update:model-value="$emit('update', { enabled: $event })"
        @keydown.enter.prevent="toggleEnabled"
        @keydown.space.prevent="toggleEnabled"
      />
    </header>
    <div v-if="serviceType" class="agent-trigger-card__body">
      <div
        class="agent-trigger-card__section agent-trigger-card__configuration"
      >
        <Alert
          v-if="needsWorkspaceAccess"
          type="info-primary"
          class="agent-trigger-card__note"
        >
          {{ $t('agent.triggerNeedsWorkspaceAccess') }}
        </Alert>
        <div class="agent-trigger-card__service">
          <component
            :is="serviceType.formComponent"
            v-if="typeOptions"
            ref="form"
            :key="`${trigger.type}:${typesVersion}:${serviceReverts}`"
            v-bind="formChoices || {}"
            :application="agent"
            :service="trigger.service"
            :service-type="serviceType"
            :default-values="trigger.service"
            :loading="saving"
            @values-changed="onServiceValuesChanged"
          />
        </div>
        <p v-if="serviceError" class="agent-trigger-card__error" role="alert">
          {{ serviceError }}
        </p>
        <FormGroup
          v-if="serviceType.returnsList(trigger.service)"
          class="agent-trigger-card__batch-size"
          :label="$t('agent.triggerBatchSize')"
          :helper-text="$t('agent.triggerBatchSizeHelper')"
          :error-message="batchSizeError"
          small-label
          required
        >
          <FormInput
            type="number"
            :min="1"
            :max="TRIGGER_MAX_BATCH_SIZE"
            :model-value="batchSizeText"
            :error="Boolean(batchSizeError)"
            :disabled="!editable"
            @update:model-value="onBatchSizeInput"
            @blur="onBatchSizeBlur"
          />
        </FormGroup>
      </div>
      <div class="agent-trigger-card__section">
        <FormGroup
          class="agent-trigger-card__message"
          :label="$t('agent.triggerMessage')"
          :help-icon-tooltip="$t('agent.triggerMessageHelper')"
          small-label
        >
          <AgentTriggerMessageInput
            :model-value="trigger.message"
            :disabled="!editable"
            :placeholder="$t('agent.triggerMessagePlaceholder')"
            @update:model-value="$emit('update', { message: $event })"
          />
        </FormGroup>
        <Expandable
          v-if="schemaProperties.length"
          class="agent-trigger-card__schema"
        >
          <template #header="{ expanded, toggle }">
            <button
              type="button"
              class="agent-trigger-card__schema-toggle"
              :aria-expanded="expanded"
              @click="toggle"
            >
              <span class="agent-trigger-card__schema-title">
                {{ $t('agent.triggerDataProvides') }}
              </span>
              <span class="agent-trigger-card__schema-count">
                {{
                  $t('agent.triggerDataValues', {
                    count: schemaProperties.length,
                  })
                }}
              </span>
              <i
                class="agent-trigger-card__schema-chevron"
                :class="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                aria-hidden="true"
              ></i>
            </button>
          </template>
          <ul class="agent-trigger-card__schema-list">
            <li v-for="property in schemaProperties" :key="property.key">
              <span>{{ property.title }}</span>
              <span class="agent-trigger-card__schema-type">{{
                property.type
              }}</span>
            </li>
          </ul>
        </Expandable>
      </div>
      <div class="agent-trigger-card__section agent-trigger-card__overlap">
        <div
          :id="`${overlapId}-title`"
          class="agent-trigger-card__overlap-title"
        >
          {{ $t('agent.triggerOnOverlap') }}
        </div>
        <p
          :id="`${overlapId}-description`"
          class="agent-trigger-card__overlap-description"
        >
          {{ $t('agent.triggerOnOverlapDescription') }}
        </p>
        <div
          class="agent-trigger-card__overlap-options"
          role="radiogroup"
          :aria-labelledby="`${overlapId}-title`"
          :aria-describedby="`${overlapId}-description`"
        >
          <Radio
            v-for="option in TRIGGER_OVERLAP_OPTIONS"
            :key="option.value"
            class="agent-trigger-card__overlap-option"
            :name="overlapId"
            :value="option.value"
            :model-value="trigger.on_overlap"
            :disabled="!editable"
            @update:model-value="$emit('update', { on_overlap: $event })"
          >
            <div class="agent-trigger-card__overlap-option-text">
              <div class="agent-trigger-card__overlap-option-label">
                {{ $t(option.label) }}
                <Badge
                  v-if="option.value === defaultOnOverlap"
                  color="green"
                  size="small"
                >
                  {{ $t('agent.triggerOnOverlapRecommended') }}
                </Badge>
              </div>
              <div class="agent-trigger-card__overlap-option-hint">
                {{ overlapHint(option) }}
              </div>
            </div>
          </Radio>
        </div>
        <p v-if="skippedText" class="agent-trigger-card__skipped" role="status">
          {{ skippedText }}
        </p>
      </div>
    </div>
    <footer v-if="editable" class="agent-trigger-card__footer">
      <ButtonText
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        class="agent-trigger-card__delete"
        @click="$emit('delete')"
      >
        {{ $t('agent.deleteTrigger') }}
      </ButtonText>
    </footer>
    <AgentTriggerPicker
      v-if="editable"
      ref="typePicker"
      :available-types="availableTypes"
      :workspace="workspace"
      @select="$emit('change-type', $event)"
    />
  </article>
</template>

<script setup>
import {
  computed,
  inject,
  nextTick,
  provide,
  reactive,
  ref,
  toRef,
  useId,
  watch,
} from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import Editable from '@baserow/modules/core/components/Editable'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import AgentTriggerMessageInput from '@baserow/modules/agent/components/configuration/AgentTriggerMessageInput'
import AgentTriggerPicker from '@baserow/modules/agent/components/configuration/AgentTriggerPicker'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'
import moment from '@baserow/modules/core/moment'
import {
  TRIGGER_MAX_BATCH_SIZE,
  TRIGGER_NAME_MAX_LENGTH,
  TRIGGER_OVERLAP_OPTIONS,
  TRIGGER_SKIP_REASON_TEXT,
} from '@baserow/modules/agent/constants'

const props = defineProps({
  /** The trigger as the card shows it, edits included. */
  trigger: { type: Object, required: true },
  /** The Agent's workspace, for the hosted service form. */
  workspace: { type: Object, default: null },
  /** Whether the user may change the trigger. */
  editable: Boolean,
  /** Whether a save of the trigger is in flight. */
  saving: Boolean,
  /** How many runs of a waiting trigger the server queues, for its hint. */
  maxQueuedTriggerRuns: { type: Number, default: null },
  /** How many runs of a trigger that runs in parallel can go at once; 0 or less is no limit. */
  maxParallelTriggerRuns: { type: Number, default: null },
  /** Why the server rejected the service values, or ''. */
  serviceError: { type: String, default: '' },
  /** How often a failed save reverted the service values the form shows. */
  serviceReverts: { type: Number, default: 0 },
  /** What the run identity offers this trigger's type, or null while it loads. */
  typeOptions: { type: Object, default: null },
  /** Changes whenever the type options reload, to remount the hosted form. */
  typesVersion: { type: Number, default: 0 },
  /** Whether the Agent acts as a workspace identity that is available. */
  runAsActive: Boolean,
  /** The trigger types the Agent's configuration offers, to change to. */
  availableTypes: { type: Array, default: () => [] },
})
const emit = defineEmits(['update', 'change-type', 'delete'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
const agent = inject('agentApplication')
const form = ref(null)
const typePicker = ref(null)
const nameEditable = ref(null)
const renaming = ref(false)
const overlapId = useId()
const serviceType = computed(() => serviceTypeOf($registry, props.trigger.type))
// Hosted service forms inject these like in Automation's node side panel.
provide('formulaComponent', FormulaInputField)
provide('dataProvidersAllowed', [])
provide('workspace', toRef(props, 'workspace'))
provide(
  'applicationContext',
  reactive({
    get agent() {
      return agent.value
    },
    get trigger() {
      return props.trigger
    },
  })
)
const formChoices = computed(() => props.typeOptions?.form_choices ?? null)
const typeName = computed(() => serviceType.value?.name || props.trigger.type)
const defaultName = computed(
  () =>
    serviceType.value?.getDefaultName(
      props.trigger.service,
      formChoices.value || {}
    ) || props.trigger.type
)
const shownName = computed(() => props.trigger.name || defaultName.value)
const defaultOnOverlap = computed(
  () => props.typeOptions?.default_on_overlap ?? null
)
/** A form that reads workspace data has nothing to offer without an identity. */
const needsWorkspaceAccess = computed(
  () => formChoices.value !== null && !props.runAsActive
)
const configurationError = computed(
  () =>
    serviceType.value?.getErrorMessage({
      service: props.trigger.service,
      workspace: props.workspace,
    }) || ''
)
const isUnlimited = (cap) => cap !== null && cap <= 0
/** The hint of an overlap option, worded by the caps it counts; 0 is no limit. */
const overlapHint = (option) => {
  const queued = props.maxQueuedTriggerRuns
  const count =
    option.cap === 'parallel' ? props.maxParallelTriggerRuns : queued
  if (isUnlimited(count) && option.unlimitedHint) {
    return t(option.unlimitedHint)
  }
  if (isUnlimited(queued) && option.queueUnlimitedHint) {
    return t(option.queueUnlimitedHint, { count })
  }
  return t(option.hint, { count, queued })
}
/** Why the last firing started nothing, until a later firing is accepted. */
const skippedText = computed(() => {
  const {
    last_skipped_on: skippedOn,
    last_fired_on: firedOn,
    last_skipped_reason: reason,
  } = props.trigger
  const reasonText = TRIGGER_SKIP_REASON_TEXT[reason]
  if (
    !skippedOn ||
    !reasonText ||
    (firedOn && !moment(skippedOn).isAfter(firedOn))
  ) {
    return ''
  }
  const skipped = moment(skippedOn)
  const format = skipped.isSame(moment(), 'day') ? 'LT' : 'L LT'
  return t(reasonText, { time: skipped.format(format) })
})
const schemaProperties = computed(() => {
  const schema = $registry
    .get('agentDataProvider', 'trigger')
    .getDataSchema({ trigger: props.trigger })
  return Object.entries(schema?.properties || {}).map(([key, property]) => ({
    key,
    title: property.title || key,
    type: property.type,
  }))
})

const batchSizeText = ref(String(props.trigger.batch_size ?? ''))
let batchSizeBeforeEdit = null
/**
 * @param {string} text The typed batch size.
 * @returns {number|null} The batch size, or null when the server would refuse it.
 */
const parseBatchSize = (text) => {
  const size = /^\d+$/.test(text) ? Number(text) : 0
  return size >= 1 && size <= TRIGGER_MAX_BATCH_SIZE ? size : null
}
const batchSizeError = computed(() =>
  parseBatchSize(batchSizeText.value) === null
    ? t('agent.triggerBatchSizeInvalid', { max: TRIGGER_MAX_BATCH_SIZE })
    : ''
)
// An invalid entry stays on screen for the user to fix until the input blurs.
watch(
  () => props.trigger.batch_size,
  (size) => {
    const typed = parseBatchSize(batchSizeText.value)
    if (typed !== null && typed !== size) batchSizeText.value = String(size)
  }
)

function onServiceValuesChanged(values) {
  if (!props.editable) return
  if (form.value?.isFormValid && !form.value.isFormValid()) return
  emit('update', { service: values })
}

/**
 * Shows the typed batch size and saves it once it's valid. An invalid one takes
 * back the sizes typed on the way to it, like 15 on the way to 150.
 *
 * @param {string} value The typed value.
 */
function onBatchSizeInput(value) {
  if (batchSizeBeforeEdit === null) {
    batchSizeBeforeEdit = props.trigger.batch_size
  }
  batchSizeText.value = String(value)
  const size = parseBatchSize(batchSizeText.value) ?? batchSizeBeforeEdit
  if (size !== props.trigger.batch_size) emit('update', { batch_size: size })
}

/** Shows the batch size that is kept again when the typed one is invalid. */
function onBatchSizeBlur() {
  batchSizeBeforeEdit = null
  if (parseBatchSize(batchSizeText.value) === null) {
    batchSizeText.value = String(props.trigger.batch_size)
  }
}

function startRename() {
  if (props.editable && !renaming.value) nameEditable.value.edit()
}

/**
 * Saves the typed name; a blank one, or the default, clears the name so the
 * default follows the trigger's settings.
 *
 * @param {object} event The Editable's change, with the typed `value`.
 */
function rename({ value }) {
  const typed = Array.from(value.trim())
    .slice(0, TRIGGER_NAME_MAX_LENGTH)
    .join('')
  emit('update', { name: typed === defaultName.value ? '' : typed })
  // An unchanged shown name, like a cleared default, doesn't reset the edited text.
  nextTick(() => nameEditable.value?.set())
}

function toggleEnabled() {
  if (props.editable) emit('update', { enabled: !props.trigger.enabled })
}
</script>
