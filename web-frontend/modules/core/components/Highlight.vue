<template>
  <div
    v-if="selector !== null"
    class="highlight"
    :style="{
      left: `${position.left || '0px'}`,
      top: `${position.top || '0px'}`,
      width: `${position.width || '0px'}`,
      height: `${position.height || '0px'}`,
    }"
  >
    <slot></slot>
  </div>
</template>

<script>
import {
  findScrollableParent,
  getCombinedBoundingClientRect,
} from '@baserow/modules/core/utils/dom'

export default {
  name: 'Highlight',
  props: {
    getParent: {
      type: Function,
      required: false,
      default: null,
    },
    padding: {
      type: Number,
      required: false,
      default: 2,
    },
  },
  data() {
    return {
      scrollableParents: new Set(),
      selector: null,
      position: {
        top: 0,
        right: 0,
        width: 0,
        height: 0,
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
    this.clearScrollEvents()
  },
  methods: {
    _getParent() {
      return this.getParent !== null ? this.getParent() : this.$el.parentElement
    },
    clearScrollEvents() {
      this.scrollableParents.forEach((element) => {
        element.removeEventListener('scroll', this.update)
      })
      this.scrollableParents = new Set()
    },
    getElements(selector) {
      const parent = this._getParent()
      const selectors = Array.isArray(selector)
        ? this.selector
        : [this.selector]
      const elements = selectors
        .map((selector) => parent.querySelector(selector))
        .filter((element) => !!element)
      return elements
    },
    show(selector) {
      this.selector = selector
      this.update()
      this.clearScrollEvents()
      this.getElements(selector).forEach((element) => {
        const scrollableParent = findScrollableParent(element)
        if (scrollableParent) {
          this.scrollableParents.add(scrollableParent)
          scrollableParent.addEventListener('scroll', this.update)
        }
        element.scrollIntoView({
          behavior: 'smooth',
          inline: 'center',
          block: 'center',
        })
      })
    },
    update() {
      const position = {
        left: '0px',
        top: '0px',
        width: '0px',
        height: '0px',
      }

      if (this.selector === null) {
        return
      }

      if (this.selector.length > 0) {
        const elements = this.getElements(this.selector)
        const parentRect = this._getParent().getBoundingClientRect()
        const elementRect = getCombinedBoundingClientRect(elements)
        position.top = elementRect.top - parentRect.top - this.padding + 'px'
        position.left = elementRect.left - parentRect.left - this.padding + 'px'
        position.width = elementRect.width + this.padding * 2 + 'px'
        position.height = elementRect.height + this.padding * 2 + 'px'
      } else {
        position.top = '50%'
        position.left = '50%'
      }

      this.position = position
    },
    hide() {
      this.selector = null
      this.clearScrollEvents()
    },
  },
}
</script>
