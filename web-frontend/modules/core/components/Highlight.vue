<template>
  <div
    v-if="selector !== null"
    class="highlight"
    :style="{
      left: `${position.left || 0}px`,
      top: `${position.top || 0}px`,
      width: `${position.width || 0}px`,
      height: `${position.height || 0}px`,
    }"
  >
    <slot></slot>
  </div>
</template>

<script>
import { getCombinedBoundingClientRect } from '@baserow/modules/core/utils/dom'

export default {
  name: 'Highlight',
  props: {
    getParent: {
      type: Function,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      selector: null,
      position: {
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
      },
    }
  },
  mounted() {
    const parent = this._getParent()
    this.resizeObserver = new ResizeObserver(() => {
      this.update()
    })
    this.resizeObserver.observe(parent)
    this.update()
  },
  beforeDestroy() {
    const parent = this._getParent()
    this.resizeObserver.unobserve(parent)
  },
  methods: {
    _getParent() {
      return this.getParent !== null ? this.getParent() : this.$el.parentElement
    },
    show(selector) {
      this.selector = selector
      this.update()
    },
    update() {
      if (this.selector === null) {
        return
      }

      const position = {
        left: 0,
        top: 0,
        width: 0,
        height: 0,
      }
      const parent = this._getParent()

      const selectors = Array.isArray(this.selector)
        ? this.selector
        : [this.selector]
      const elements = selectors
        .map((selector) => parent.querySelector(selector))
        .filter((element) => !!element)
      const parentRect = parent.getBoundingClientRect()
      const elementRect = getCombinedBoundingClientRect(elements)
      const padding = 2
      position.top = elementRect.top - parentRect.top - padding
      position.left = elementRect.left - parentRect.left - padding
      position.width = elementRect.width + padding * 2
      position.height = elementRect.height + padding * 2

      this.position = position
    },
    hide() {
      this.selector = null
    },
  },
}
</script>
