<template>
  <div
    ref="colorPicker"
    class="color-picker"
    :style="{
      '--vacp-hsl-h': colors.hsl.h,
      '--vacp-hsl-s': colors.hsl.s,
      '--vacp-hsl-l': colors.hsl.l,
      '--vacp-hsl-a': colors.hsl.a,
      // Added this style via the style because scss doesn't support
      // this one, it fails because of a `hsl` function not found.
      '--vacp-color':
        'hsl(calc(var(--vacp-hsl-h) * 360) calc(var(--vacp-hsl-s) * 100%) calc(var(--vacp-hsl-l) * 100%))',
    }"
  >
    <div
      ref="colorSpace"
      class="color-picker__space"
      draggable="false"
      :style="{
        'background-color': 'hsl(calc(var(--vacp-hsl-h) * 360) 100% 50%)',
      }"
      @mousedown="startMovingThumbWithMouse($event, MOVE_EVENT.COLOR)"
      @touchstart="startMovingThumbWithTouch($event, MOVE_EVENT.COLOR)"
    >
      <div
        class="color-picker__thumb color-picker__thumb--negative-left-margin color-picker__thumb--negative-bottom-margin"
        :style="{
          left: `${colors.hsv.s * 100}%`,
          bottom: `${colors.hsv.v * 100}%`,
        }"
      />
    </div>
    <div
      ref="hueSpace"
      class="color-picker__slider color-picker__slider--hue color-picker__thumb--negative-bottom-margin"
      draggable="false"
      @mousedown="startMovingThumbWithMouse($event, MOVE_EVENT.HUE)"
      @touchstart="startMovingThumbWithMouse($event, MOVE_EVENT.HUE)"
    >
      <div
        class="color-picker__thumb"
        :style="{
          bottom: `${colors.hsv.h * 100}%`,
        }"
      />
    </div>
    <div
      v-if="allowOpacity"
      ref="alphaSpace"
      class="color-picker__slider color-picker__slider--alpha color-picker__thumb--negative-bottom-margin"
      draggable="false"
      @mousedown="startMovingThumbWithMouse($event, MOVE_EVENT.ALPHA)"
      @touchstart="startMovingThumbWithMouse($event, MOVE_EVENT.ALPHA)"
    >
      <div
        class="color-picker__thumb"
        :style="{
          bottom: `${colors.hsv.a * 100}%`,
        }"
      />
    </div>
  </div>
</template>

<script>
import _ from 'lodash'

import { clone } from '@baserow/modules/core/utils/object'
import { clamp } from '@baserow/modules/core/utils/number'
import {
  conversionsMap,
  isValidHexColor,
} from '@baserow/modules/core/utils/colors'

export const MOVE_EVENT = {
  COLOR: 'color',
  HUE: 'hue',
  ALPHA: 'alpha',
}

export const DEFAULT_COLOR_PICKER_COLOR = '#ffffffff'

/**
 * This color picker is inspired by
 * https://github.com/kleinfreund/vue-accessible-color-picker.
 */
export default {
  name: 'ColorPicker',
  props: {
    /**
     * The model value of the textarea in Vue 3 style.
     */
    modelValue: {
      type: String,
      default: undefined,
    },
    /**
     * The model value of the textarea in Vue 2 style.
     */
    value: {
      type: String,
      default: undefined,
    },
    allowOpacity: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  emits: ['input', 'update:modelValue'],
  data() {
    return {
      // This variable is used to figure out whether a mouse/touch move event
      // originated from. This is needed for the drag and drop of the thumbs.
      pointerOriginatedIn: '',
      // Representation of the color value in all formats.
      colors: {
        hex: DEFAULT_COLOR_PICKER_COLOR,
        hsl: { h: 0, s: 0, l: 1, a: 1 },
        hsv: { h: 0, s: 0, v: 1, a: 1 },
        rgb: { r: 1, g: 1, b: 1, a: 1 },
      },
    }
  },
  computed: {
    MOVE_EVENT: () => MOVE_EVENT,
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  watch: {
    currentValue: {
      handler(value) {
        this.setColorFromValue(value)
      },
      immediate: true,
    },
  },
  mounted() {
    document.addEventListener('mousemove', this.moveThumbWithMouse, {
      passive: false,
    })
    document.addEventListener('touchmove', this.moveThumbWithTouch, {
      passive: false,
    })
    document.addEventListener('mouseup', this.stopMovingThumb)
    document.addEventListener('touchend', this.stopMovingThumb)
  },
  beforeUnmount() {
    document.removeEventListener('mousemove', this.moveThumbWithMouse)
    document.removeEventListener('touchmove', this.moveThumbWithTouch)
    document.removeEventListener('mouseup', this.stopMovingThumb)
    document.removeEventListener('touchend', this.stopMovingThumb)
  },
  methods: {
    startMovingThumbWithMouse(event, originatedIn) {
      this.pointerOriginatedIn = originatedIn
      this.moveThumbWithMouse(event)
    },
    startMovingThumbWithTouch(event, originatedIn) {
      this.pointerOriginatedIn = originatedIn
      this.moveThumbWithTouch(event)
    },
    stopMovingThumb() {
      this.pointerOriginatedIn = ''
    },
    moveThumbWithMouse(event) {
      if (event.buttons !== 1) {
        return
      }

      this.moveThumb(event.clientX, event.clientY)
    },
    moveThumbWithTouch(event) {
      // Prevents touch events from dragging the page.
      event.preventDefault()

      const touchPoint = event.touches[0]
      this.moveThumb(touchPoint.clientX, touchPoint.clientY)
    },
    moveThumb(clientX, clientY) {
      if (this.pointerOriginatedIn === '') {
        return
      }

      const hsvColor = clone(this.colors.hsv)

      if (this.pointerOriginatedIn === MOVE_EVENT.COLOR) {
        const newThumbPosition = this.getNewThumbPosition(
          this.$refs.colorSpace,
          clientX,
          clientY
        )
        hsvColor.s = newThumbPosition.x
        hsvColor.v = newThumbPosition.y
      } else if (this.pointerOriginatedIn === MOVE_EVENT.HUE) {
        const newThumbPosition = this.getNewThumbPosition(
          this.$refs.hueSpace,
          clientX,
          clientY
        )
        hsvColor.h = Math.round(newThumbPosition.y * 100) / 100
      } else if (this.pointerOriginatedIn === MOVE_EVENT.ALPHA) {
        const newThumbPosition = this.getNewThumbPosition(
          this.$refs.alphaSpace,
          clientX,
          clientY
        )
        hsvColor.a = Math.round(newThumbPosition.y * 100) / 100
      }

      this.setColor('hsv', hsvColor)
    },
    getNewThumbPosition(colorSpace, clientX, clientY) {
      const rect = colorSpace.getBoundingClientRect()
      const x = clientX - rect.left
      const y = clientY - rect.top

      return {
        x: rect.width === 0 ? 0 : clamp(x / rect.width, 0, 1),
        y: rect.height === 0 ? 0 : clamp(1 - y / rect.height, 0, 1),
      }
    },
    setColorFromValue(value) {
      if (isValidHexColor(value)) {
        this.setColor('hex', value, false)
      }
    },
    setColor(format, color, emit = true) {
      if (!_.isEqual(this.colors[format], color)) {
        this.applyColorUpdates(format, color)
      }

      if (emit) {
        // emitting the updated value Vue 3 style.
        this.$emit('update:modelValue', this.colors.hex)
        // emitting the updated value Vue 2 style.
        this.$emit('input', this.colors.hex)
      }
    },
    applyColorUpdates(sourceFormat, newColor) {
      this.colors[sourceFormat] = newColor

      for (const [format, convert] of Object.entries(
        conversionsMap[sourceFormat]
      )) {
        this.colors[format] = convert(this.colors[sourceFormat])
      }
    },
  },
}
</script>
