<template>
  <FormElement
    :error="hasError"
    class="control"
    :class="{
      'control--horizontal':
        horizontal || horizontalNarrow || horizontalVariable,
      'control--horizontal-narrow': horizontalNarrow,
      'control--horizontal-variable': horizontalVariable,
      'control--messages': hasMessages,
      'control--after-input': hasAfterInputSlot,
      'control--error': hasError,
    }"
  >
    <label
      v-if="label && !hasLabelSlot"
      :for="forInput"
      class="control__label"
      :class="{ 'control__label--small': smallLabel }"
    >
      <span>{{ label }}</span>
      <span v-if="!required" class="control__required">
        {{ $t('common.optional') }}
      </span>
      <HelpIcon
        v-if="helpIconTooltip"
        :tooltip="helpIconTooltip"
        tooltip-content-type="plain"
        :tooltip-content-classes="[
          'tooltip__content--expandable',
          'tooltip__content--expandable-plain-text',
        ]"
        icon="info-empty"
      />
      <span v-if="hasAfterLabelSlot" class="control__after-label">
        <slot name="after-label" />
      </span>
    </label>

    <span
      v-else-if="!label && hasLabelSlot"
      class="control__label"
      :class="{ 'control__label--small': smallLabel }"
    >
      <slot name="label"></slot>
      <span v-if="hasAfterLabelSlot" class="control__after-label">
        <slot name="after-label" />
      </span>
    </span>

    <div v-if="protectedEdit && !protectedEditValue">
      <a @click="enableProtectedEdit">{{ $t('formGroup.protectedField') }}</a>
    </div>

    <div v-else class="control__wrapper">
      <div
        class="control__elements"
        :class="{ 'control__elements--flex': $slots['after-input'] }"
      >
        <div class="control__elements-wrapper"><slot /></div>

        <div v-if="protectedEdit && protectedEditValue" class="margin-top-1">
          <a @click="disableProtectedEdit">
            {{ $t('formGroup.cancelProtectedField') }}
          </a>
        </div>

        <slot name="after-input"></slot>
      </div>

      <div v-if="hasMessages" class="control__messages">
        <p v-if="helperText || hasHelperSlot" class="control__helper-text">
          {{ helperText }}
          <slot v-if="hasHelperSlot" name="helper" />
        </p>

        <p v-if="hasError" class="control__messages--error">
          <slot v-if="hasErrorSlot" name="error" />
          <template v-else-if="errorMessage">{{ errorMessage }}</template>
        </p>

        <p v-if="hasWarningSlot" class="control__messages--warning">
          <slot name="warning" />
        </p>
      </div>
    </div>
  </FormElement>
</template>

<script setup>
import { useId } from '#app'

// Props
const props = defineProps({
  /**
   * Must be set to true to display the error slot.
   */
  error: Boolean,
  /**
   * Shorthand when you don't need a specific error display.
   */
  errorMessage: { type: String, default: '' },
  /**
   * The label of the form group.
   */
  label: { type: String, default: null },
  /**
   * Whether the label should be displayed as a small label.
   */
  smallLabel: Boolean,
  /**
   * If true the label and the input will be displayed horizontally.
   */
  horizontal: Boolean,
  /**
   * If true the label and the input will be displayed horizontally but in a narrow
   * space.
   */
  horizontalNarrow: Boolean,
  /**
   * If true the label and the input will be displayed horizontally but with closer spacing.
   */
  horizontalVariable: Boolean,
  /**
   * Whether the label is required. (if false that will display an 'optional' label)
   */
  required: Boolean,
  /**
   * The helper text of the form group.
   */
  helperText: { type: String, default: null },
  helpIconTooltip: { type: String, default: '' },
  /**
   * If set to `true`, then it's not possible to change the value unless the user
   * clicks a link first.
   */
  protectedEdit: Boolean,
})

// Emit
const emit = defineEmits(['enabled-protected-edit', 'disable-protected-edit'])

// SSR-safe ID
const forInput = useId()

// Provide
provide('forInput', forInput)

// Reactive state
const protectedEditValue = ref(false)

// Slots
const slots = useSlots()

// Computed
const hasError = computed(
  () => Boolean(props.error) || Boolean(props.errorMessage)
)

const hasErrorSlot = computed(() => Boolean(slots.error))
const hasLabelSlot = computed(() => Boolean(slots.label))
const hasAfterLabelSlot = computed(() => Boolean(slots['after-label']))
const hasWarningSlot = computed(() => Boolean(slots.warning))
const hasHelperSlot = computed(() => Boolean(slots.helper))
const hasAfterInputSlot = computed(() =>
  Object.prototype.hasOwnProperty.call(slots, 'after-input')
)

const hasMessages = computed(
  () =>
    hasError.value ||
    props.helperText ||
    hasWarningSlot.value ||
    hasHelperSlot.value
)

// Methods
function enableProtectedEdit() {
  protectedEditValue.value = true
  emit('enabled-protected-edit')
}

function disableProtectedEdit() {
  protectedEditValue.value = false
  emit('disable-protected-edit')
}
</script>
