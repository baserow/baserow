export const dimensionMixin = {
  data() {
    return {
      dimensions: {
        targetElement: null,
        width: 1920,
        height: 1080,
      },
    }
  },
  mounted() {
    // Gives you time to set the targetElement in the mounted function of the component
    // using this mixin
    this.$nextTick(() => {
      this.dimensions.targetElement = this.dimensions.targetElement || this.$el
      this.resizeObserver = new ResizeObserver(this.updateElementSize)
      this.resizeObserver.observe(this.dimensions.targetElement)
    })
  },
  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
  },
  methods: {
    updateElementSize(entries) {
      for (const entry of entries) {
        if (entry.target === this.dimensions.targetElement) {
          const { width, height } = entry.contentRect
          this.dimensions.width = width
          this.dimensions.height = height
        }
      }
    },
  },
}
