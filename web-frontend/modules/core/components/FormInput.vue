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
  label: { type: String, default: '' },
  size: {
    type: String,
    default: 'regular',
    validator: (v) => ['regular', 'small', 'large', 'xlarge'].includes(v),
  },
  placeholder: { default: '', type: String },

  /* Legacy + new v-model */
  value: { default: undefined, validator: () => true },
  modelValue: { default: undefined, validator: () => true },

  toValue: { type: Function, default: (v) => v },
  fromValue: { type: Function, default: (v) => v },
  defaultValueWhenEmpty: { type: [Number, String], default: null },

  type: { type: String, default: 'text' },
  disabled: Boolean,
  monospace: Boolean,
  loading: Boolean,
  iconLeft: { type: String, default: '' },
  iconRight: { type: String, default: '' },
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
  if (!input.value) {
    // The FormInput element was unmounted in the meantime. It happens in the login
    // form for instance if you hit enter after filling the form.
    return
  }

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

function blur() {
  input.value?.blur()
}

const slots = useSlots()
const hasSuffixSlot = computed(() => !!slots.suffix)

defineExpose({ focus, blur })
</script>
