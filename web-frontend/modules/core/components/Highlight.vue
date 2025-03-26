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
  ></div>
</template>

<script>
export default {
  name: 'Highlight',
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
    const parent = this.getParent()
    this.resizeObserver = new ResizeObserver(() => {
      this.update()
    })
    this.resizeObserver.observe(parent)
    this.update()
  },
  beforeDestroy() {
    const parent = this.getParent()
    this.resizeObserver.unobserve(parent)
  },
  methods: {
    getParent() {
      return this.$el.parentElement
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
      const parent = this.getParent()

      const element = this.$parent.$el.querySelector(this.selector)
      if (element) {
        const parentRect = parent.getBoundingClientRect()
        const elementRect = element.getBoundingClientRect()
        const padding = 2
        position.top = elementRect.top - parentRect.top - padding
        position.left = elementRect.left - parentRect.left - padding
        position.width = elementRect.width + padding * 2
        position.height = elementRect.height + padding * 2
      }

      this.position = position
    },
    hide() {
      this.selector = null
    },
  },
}
</script>
