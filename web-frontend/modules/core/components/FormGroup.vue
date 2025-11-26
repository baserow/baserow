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
      <span v-if="!required" class="control__required">{{
        $t('common.optional')
      }}</span>
      <HelpIcon
        v-if="helpIconTooltip"
        :tooltip="helpIconTooltip"
        :tooltip-content-type="'plain'"
        :tooltip-content-classes="[
          'tooltip__content--expandable',
          'tooltip__content--expandable-plain-text',
        ]"
        :icon="'info-empty'"
      />
      <span v-if="hasAfterLabelSlot" class="control__after-label"
        ><slot name="after-label"
      /></span>
    </label>

    <span
      v-if="!label && hasLabelSlot"
      class="control__label"
      :class="{ 'control__label--small': smallLabel }"
    >
      <slot name="label"></slot>
      <span v-if="hasAfterLabelSlot" class="control__after-label"
        ><slot name="after-label"
      /></span>
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
          <a @click="disableProtectedEdit">{{
            $t('formGroup.cancelProtectedField')
          }}</a>
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

<script>
import { uuid } from '@baserow/modules/core/utils/string'
export default {
  name: 'FormGroup',
  provide() {
    return { forInput: this.forInput }
  },
  props: {
    /**
     * Must be set to true to display the error slot.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Shorthand when you don't need a specific error display.
     */
    errorMessage: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * The label of the form group.
     */
    label: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * Whether the label should be displayed as a small label.
     */
    smallLabel: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true the label and the input will be displayed horizontally.
     */
    horizontal: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true the label and the input will be displayed horizontally but in a narrow
     * space.
     */
    horizontalNarrow: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true the label and the input will be displayed horizontally but with closer spacing.
     */
    horizontalVariable: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the label is required. (if false that will display an 'optional' label)
     */
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The helper text of the form group.
     */
    helperText: {
      type: String,
      required: false,
      default: null,
    },
    helpIconTooltip: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * If set to `true`, then it's not possible to change the value unless the user
     * clicks a link first.
     */
    protectedEdit: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      protectedEditValue: false,
      forInput: uuid(),
    }
  },
  computed: {
    hasError() {
      return Boolean(this.error) || Boolean(this.errorMessage)
    },
    hasErrorSlot() {
      return !!this.$slots.error
    },
    hasLabelSlot() {
      return !!this.$slots.label
    },
    hasAfterLabelSlot() {
      return !!this.$slots['after-label']
    },
    hasWarningSlot() {
      return !!this.$slots.warning
    },
    hasHelperSlot() {
      return !!this.$slots.helper
    },
    hasAfterInputSlot() {
      return Object.prototype.hasOwnProperty.call(this.$slots, 'after-input')
    },
    hasMessages() {
      return (
        this.hasError ||
        this.helperText ||
        this.hasWarningSlot ||
        this.hasHelperSlot
      )
    },
  },
  methods: {
    enableProtectedEdit() {
      this.protectedEditValue = true
      this.$emit('enabled-protected-edit')
    },
    disableProtectedEdit() {
      this.protectedEditValue = false
      this.$emit('disable-protected-edit')
    },
  },
}
</script>
