<template>
  <div class="checkbox" :class="classNames" @click="toggle(checked)">
    <div class="checkbox__button">
      <svg
        v-show="checked && !indeterminate"
        class="checkbox__tick"
        xmlns="http://www.w3.org/2000/svg"
        width="9"
        height="8"
        viewBox="0 0 9 8"
        fill="none"
      >
        <g :clip-path="`url(#${clipPathId})`">
          <path
            d="M1.5179 4.4821L3.18211 6.18211L7.42475 2.15368"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </g>
        <defs>
          <clipPath :id="clipPathId">
            <rect
              width="8"
              height="8"
              fill="white"
              transform="translate(0.5)"
            />
          </clipPath>
        </defs>
      </svg>
      <svg
        v-show="indeterminate"
        class="checkbox__tick-indeterminate"
        xmlns="http://www.w3.org/2000/svg"
        width="8"
        height="8"
        viewBox="0 0 8 8"
        fill="none"
      >
        <path
          d="M1.5 4L6.5 4"
          stroke="white"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>
    <label v-if="hasSlot" class="checkbox__label">
      <slot></slot>
    </label>
  </div>
</template>

<script>
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'Checkbox',
  model: {
    prop: 'checked',
    event: 'input',
  },
  props: {
    /**
     * The state of the checkbox.
     */
    checked: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is in error state.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is in indeterminate state
     */
    indeterminate: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The size of the button.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator(value) {
        return ['small', 'regular'].includes(value)
      },
    },
  },
  data() {
    return {
      uniqClipId: uuid(),
    }
  },
  computed: {
    /**
     * The `clip-path` IDs are expected to be unique in the DOM. If we have
     * multiple checkboxes on the same page, and IDs are re-used, this can
     * lead the rendering issues where the svg isn't draw properly.
     */
    clipPathId() {
      return `clip${this.uniqClipId}`
    },
    classNames() {
      return {
        'checkbox--disabled': this.disabled,
        'checkbox--checked': this.checked,
        'checkbox--indeterminate': this.indeterminate,
        'checkbox--error': this.error,
        'checkbox--small': this.size === 'small',
      }
    },
    hasSlot() {
      return !!this.$slots.default
    },
  },
  methods: {
    toggle(checked) {
      if (this.disabled) return

      this.$emit('input', !checked)
    },
  },
}
</script>
