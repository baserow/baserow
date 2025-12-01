<template>
  <div :class="{ dragging: dragging }" @mousedown.stop="start($event)"></div>
</template>

<script>
export default {
  name: 'HorizontalResize',
  props: {
    width: {
      type: Number,
      required: true,
    },
    min: {
      type: Number,
      required: false,
      default: 0,
    },
    max: {
      type: [Number, null],
      required: false,
      default: null,
    },
    stopPropagation: {
      type: Boolean,
      required: false,
      default: false,
    },
    right: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      dragging: false,
      mouseStart: 0,
      startWidth: 0,
    }
  },
  methods: {
    start(event) {
      event.preventDefault()
      if (this.stopPropagation) {
        event.stopPropagation()
      }
      this.dragging = true
      this.mouseStart = event.clientX
      this.startWidth = parseFloat(this.width)

      this.$el.moveEvent = (event) => this.move(event)
      this.$el.upEvent = (event) => this.up(event)

      window.addEventListener('mousemove', this.$el.moveEvent)
      window.addEventListener('mouseup', this.$el.upEvent)
      document.body.classList.add('resizing-horizontal')
    },
    move(event) {
      event.preventDefault()
      const difference = event.clientX - this.mouseStart
      let newWidth = 0
      if (this.right) {
        newWidth = Math.max(this.startWidth - difference, this.min)
      } else {
        newWidth = Math.max(this.startWidth + difference, this.min)
      }
      if (this.max) {
        newWidth = Math.min(newWidth, this.max)
      }

      this.$emit('move', newWidth)
    },
    up(event) {
      event.preventDefault()
      this.dragging = false
      const difference = event.clientX - this.mouseStart
      const newWidth = Math.max(this.startWidth + difference, this.min)
      window.removeEventListener('mousemove', this.$el.moveEvent)
      window.removeEventListener('mouseup', this.$el.upEvent)
      document.body.classList.remove('resizing-horizontal')

      if (newWidth === this.startWidth) {
        return
      }

      this.$emit('update', { width: newWidth, oldWidth: this.startWidth })
    },
  },
}
</script>
