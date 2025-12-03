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
      'form-input--xlarge': size === 'xlarge',
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
        :id="forInput"
        ref="input"
        class="form-input__input"
        :class="{ 'form-input__input--text-invisible': textInvisible }"
        :value="fromValue(innerValue)"
        :disabled="disabled"
        :type="type"
        :min="type === 'number' && min > -1 ? parseInt(min) : false"
        :max="type === 'number' && max > -1 ? parseInt(max) : false"
        :step="type === 'number' && step > -1 ? parseFloat(step) : false"
        :placeholder="placeholder"
        :required="required"
        :autocomplete="autocomplete"
        @blur="onBlur"
        @click="$emit('click', $event)"
        @focus="$emit('focus', $event)"
        @keyup="$emit('keyup', $event)"
        @keydown="$emit('keydown', $event)"
        @keypress="$emit('keypress', $event)"
        @input.stop="onInput"
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

<script setup>
import { computed, ref, inject } from 'vue'

const props = defineProps({
  error: Boolean,
  label: String,
  size: {
    type: String,
    default: 'regular',
    validator: (v) => ['regular', 'small', 'large', 'xlarge'].includes(v),
  },
  placeholder: String,

  /* Legacy + new v-model */
  value: { default: undefined },
  modelValue: { default: undefined },

  toValue: { type: Function, default: (v) => v },
  fromValue: { type: Function, default: (v) => v },
  defaultValueWhenEmpty: { type: [Number, String], default: null },

  type: { type: String, default: 'text' },
  disabled: Boolean,
  monospace: Boolean,
  loading: Boolean,
  iconLeft: String,
  iconRight: String,
  required: Boolean,
  removeNumberInputControls: Boolean,
  autocomplete: { type: String, default: '' },
  min: { type: Number, default: -1 },
  max: { type: Number, default: -1 },
  step: { type: Number, default: -1 },
  focusOnClick: { type: Boolean, default: true },
  textInvisible: Boolean,
})

const emit = defineEmits([
  'input',
  'update:modelValue',
  'blur',
  'click',
  'focus',
  'keyup',
  'keydown',
  'keypress',
  'mouseup',
  'mousedown',
])
const forInput = inject('forInput', null)

const input = ref(null)

/* Keep compat with nuxt2 version */
const innerValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value
)

/* Unified emitter for compat with legacy usages */
function updateValue(raw) {
  const converted = props.toValue(raw)
  emit('input', converted) // legacy
  emit('update:modelValue', converted) // new v-model
}

function onInput(e) {
  const raw = input.value.value

  if (!raw && props.defaultValueWhenEmpty !== null) return

  updateValue(e.target.value)
}

function onBlur(e) {
  const raw = input.value.value

  if (!raw && props.defaultValueWhenEmpty !== null) {
    input.value.value = props.defaultValueWhenEmpty
    updateValue(props.defaultValueWhenEmpty)
  }

  emit('blur', e)
}

function focus() {
  input.value?.focus()
}

const slots = useSlots()
const hasSuffixSlot = computed(() => !!slots.suffix)
</script>

<sscript>
export default {
  name: 'FormInput',
  inject: {
    forInput: { from: 'forInput', default: null },
  },
  props: {
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
        return ['regular', 'small', 'large', 'xlarge'].includes(value)
      },
      default: 'regular',
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    value: {
      required: false,
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
  computed: {
    hasSuffixSlot() {
      return !!this.$slots.suffix
    },
  },
  methods: {
    focus() {
      this.$refs.input.focus()
      this.previousValue = this.value
    },
    blur() {
      this.$refs.input.blur()
    },
    onInput(event) {
      console.log(' input', event)
      const value = this.$refs.input.value
      if (!value && this.defaultValueWhenEmpty !== null) {
        console.log('quiiiit')
        return
      }
      console.log('eemit', this.toValue(event.target.value))
      this.$emit('input', this.toValue(event.target.value))
    },
    onBlur(event) {
      const value = this.$refs.input.value
      if (!value && this.defaultValueWhenEmpty !== null) {
        this.$refs.input.value = this.defaultValueWhenEmpty
        this.$emit('input', this.defaultValueWhenEmpty)
      }
      this.$emit('blur', event)
    },
  },
}
</sscript>
