<template>
  <div class="radio-card" :class="classNames" @click="select(value)">
    <div class="radio-card__input">
      <Radio :value="value" :model-value="modelValue" />
    </div>
    <div class="radio-card__content">
      <div class="radio-card__labels">
        <label class="radio-card__label">{{ label }}</label>
        <div v-if="badgeLabel" class="radio-card__badge">
          <Badge :rounded="true" :small="true">{{ badgeLabel }}</Badge>
        </div>
      </div>
      <div v-if="hasSlot" class="radio-card__description">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RadioCard',
  model: {
    prop: 'modelValue',
    event: 'input',
  },
  props: {
    value: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
    },
    modelValue: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
    },
    label: {
      type: String,
      required: true,
    },
    badgeLabel: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  computed: {
    classNames() {
      return {
        'radio-card--selected': this.modelValue === this.value,
      }
    },
    selected() {
      return this.modelValue === this.value
    },
    hasSlot() {
      return !!this.$slots.default
    },
  },
  methods: {
    select(value) {
      if (this.disabled || this.selected) {
        return
      }
      this.$emit('input', value)
    },
  },
}
</script>
