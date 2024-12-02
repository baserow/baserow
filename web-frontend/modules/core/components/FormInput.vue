<template>
  <div
    class="form-input"
    :class="{
      'form-input--error': error,
      'form-input--monospace': monospace,
      'form-input--icon-left': iconLeft,
      'form-input--icon-right': iconRight,
      'form-input--loading': loading,
      'form-input--disabled': disabled,
      'form-input--small': size === 'small',
      'form-input--large': size === 'large',
      'form-input--suffix': hasSuffixSlot,
      'form-input--no-controls': removeNumberInputControls,
    }"
    @click="focusOnClick && focus()"
  >
    <i
      v-if="iconLeft"
      class="form-input__icon form-input__icon-left"
      :class="iconLeft"
    />

    <div class="form-input__wrapper">
      <input
        :id="id"
        ref="input"
        class="form-input__input"
        :class="{ 'form-input__input--text-invisible': textInvisible }"
        :value="fromValue(value)"
        :disabled="disabled"
        :type="type"
        :min="type == 'number' && min > -1 ? parseInt(min) : false"
        :max="type == 'number' && max > -1 ? parseInt(max) : false"
        :step="type == 'number' && step > -1 ? parseFloat(step) : false"
        :placeholder="placeholder"
        :required="required"
        :autocomplete="autocomplete"
        @blur="onBlur($event)"
        @click="$emit('click', $event)"
        @focus="$emit('focus', $event)"
        @keyup="$emit('keyup', $event)"
        @keydown="$emit('keydown', $event)"
        @keypress="$emit('keypress', $event)"
        @input="$emit('input', toValue($event.target.value))"
        @mouseup="$emit('mouseup', $event)"
        @mousedown="$emit('mousedown', $event)"
      />
      <i
        v-if="iconRight"
        class="form-input__icon form-input__icon-right"
        :class="iconRight"
      />
    </div>

    <div v-if="hasSuffixSlot" class="form-input__suffix">
      <slot name="suffix"></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FormInput',
  props: {
    id: {
      type: String,
      required: false,
      default: null,
    },
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    label: {
      type: String,
      required: false,
      default: null,
    },
    size: {
      type: String,
      required: false,
      validator: function (value) {
        return ['regular', 'small', 'large'].includes(value)
      },
      default: 'regular',
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    value: {
      required: true,
      validator: (value) => true,
    },
    toValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    defaultValueWhenEmpty: {
      type: [Number, String],
      required: false,
      default: null,
    },
    fromValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    type: {
      type: String,
      required: false,
      default: 'text',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    monospace: {
      type: Boolean,
      required: false,
      default: false,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    iconLeft: {
      type: String,
      required: false,
      default: '',
    },
    iconRight: {
      type: String,
      required: false,
      default: '',
    },
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    removeNumberInputControls: {
      type: Boolean,
      required: false,
      default: false,
    },
    autocomplete: {
      type: String,
      required: false,
      default: '',
    },
    min: {
      type: Number,
      required: false,
      default: -1,
    },
    max: {
      type: Number,
      required: false,
      default: -1,
    },
    step: {
      type: Number,
      required: false,
      default: -1,
    },
    focusOnClick: {
      type: Boolean,
      required: false,
      default: true,
    },
    textInvisible: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {}
  },
  computed: {
    hasSuffixSlot() {
      return !!this.$slots.suffix
    },
  },
  methods: {
    focus() {
      this.$refs.input.focus()
    },
    blur() {
      this.$refs.input.blur()
    },
    /**
     * This method handles user input when the value is otherwise disallowed
     * by the `type` prop.
     *
     * The `type` prop restricts what is allowed into the input field. E.g.
     * when the `type` is Number, the user might input a minus character, which
     * needs to be handled.
     *
     * For better UX, when the user deletes the input's value it is replaced
     * with a default value when possible. This is better than displaying an
     * empty value and a validation error.
     */
    onBlur(event) {
      const value = this.$refs.input.value

      // If value is empty (e.g. user deleted the input)
      if (!value) {
        if (this.defaultValueWhenEmpty !== null) {
          this.$emit('input', this.defaultValueWhenEmpty)

          // Ensures the input's value is updated.
          this.$refs.input.value = this.defaultValueWhenEmpty
        } else {
          // If the default value is not available, then leave the value empty
          this.$emit('input', this.toValue(value))
        }
      } else {
        // Emit the valid value
        this.$emit('input', this.toValue(value))
      }
      this.$emit('blur', event)
    },
  },
}
</script>
