<template>
  <div class="scrollbars">
    <div
      v-if="vertical !== null && verticalShow"
      class="scrollbars__vertical-wrapper"
    >
      <div
        ref="scrollbarVertical"
        class="scrollbars__vertical"
        :style="{ top: verticalTop + '%', height: verticalHeight + '%' }"
        @mousedown="mouseDownVertical($event)"
      ></div>
    </div>
    <div
      v-if="horizontal !== null && horizontalShow"
      class="scrollbars__horizontal-wrapper"
    >
      <div
        ref="scrollbarHorizontal"
        class="scrollbars__horizontal"
        :style="{ left: horizontalLeft + '%', width: horizontalWidth + '%' }"
        @mousedown="mouseDownHorizontal($event)"
      ></div>
    </div>
  </div>
</template>

<script>
import { floor, ceil } from '@baserow/modules/core/utils/number'

/**
 * This component will render custom scrollbars to a scrollable div. They will
 * automatically adjust when you resize the window and can be dragged.
 */
export default {
  name: 'Scrollbars',
  props: {
    /**
     * The vertical property should be the reference of the vertical scrollable element
     * in the parent component.
     */
    vertical: {
      required: false,
      type: String,
      default: null,
    },
    /**
     * The horizontal property should be the reference of the vertical scrollable
     * element in the parent component.
     */
    horizontal: {
      required: false,
      type: String,
      default: null,
    },
  },
  emits: ['horizontal', 'vertical'],
  data() {
    return {
      dragging: null,
      elementStart: 0,
      mouseStart: 0,
      verticalShow: false,
      verticalHeight: 0,
      verticalTop: 0,
      horizontalShow: false,
      horizontalWidth: 0,
      horizontalLeft: 0,
    }
  },
  mounted() {
    this.update()

    // Register the event when the window is resized because the size of the scrollbars
    // might need to updated.
    this.$el.resizeEventListener = () => this.update()
    window.addEventListener('resize', this.$el.resizeEventListener)

    // Register the mouseup event for when the user releases the mouse button. This is
    // needed for the dragging of the scrollbar handle.
    this.$el.mouseUpEventListener = (event) => this.mouseUp(event)
    window.addEventListener('mouseup', this.$el.mouseUpEventListener)

    // Register the mousemove event for when the user moves his mouse. This is needed
    // for the dragging of the scrollbar handle.
    this.$el.mouseMoveEventListener = (event) => this.mouseMove(event)
    window.addEventListener('mousemove', this.$el.mouseMoveEventListener)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.$el.resizeEventListener)
    window.removeEventListener('mouseup', this.$el.mouseUpEventListener)
    window.removeEventListener('mousemove', this.$el.mouseMoveEventListener)
  },
  methods: {
    update() {
      if (this.vertical !== null) {
        this.updateVertical()
      }
      if (this.horizontal !== null) {
        this.updateHorizontal()
      }
    },
    /**
     * Method that updates the visibility, height and top position of the vertical
     * scrollbar handle based on the scrollTop of the vertical scrolling element of the
     * parent.
     */
    updateVertical() {
      const element = this.$parent[this.vertical]()
      const show = element.scrollHeight > element.clientHeight
      // @TODO if the client height is very high we have a minimum of 2%, but this needs
      //  to be subtracted from the top position so that it fits. Same goes for the
      //  horizontal handler.
      const height = Math.max(
        floor((element.clientHeight / element.scrollHeight) * 100, 2),
        2
      )
      const top = ceil((element.scrollTop / element.scrollHeight) * 100, 2)

      this.verticalShow = show
      this.verticalHeight = height
      this.verticalTop = top
    },
    /**
     * Method that updates the visibility, width and left position of the horizontal
     * scrollbar handle based on the scrollLeft of horizontal scrolling element of the
     * parent.
     */
    updateHorizontal() {
      const element = this.$parent[this.horizontal]()
      const show = element.scrollWidth > element.clientWidth
      const width = Math.max(
        floor((element.clientWidth / element.scrollWidth) * 100, 2),
        2
      )
      const left = ceil((element.scrollLeft / element.scrollWidth) * 100, 2)
      this.horizontalShow = show
      this.horizontalWidth = width
      this.horizontalLeft = left
    },
    /**
     * Event that is called when the user clicks on the vertical scrollbar handle. It
     * will start the vertical dragging.
     */
    mouseDownVertical(event) {
      event.preventDefault()
      this.dragging = 'vertical'
      this.elementStart = this.$refs.scrollbarVertical.offsetTop
      this.mouseStart = event.clientY
    },
    /**
     * Event that is called when the user clicks on the horizontal scrollbar handle. It
     * will start the horizontal dragging.
     */
    mouseDownHorizontal(event) {
      event.preventDefault()
      this.dragging = 'horizontal'
      this.elementStart = this.$refs.scrollbarHorizontal.offsetLeft
      this.mouseStart = event.clientX
    },
    /**
     * Event that is called when the mouse moves. If vertical of horizontal scrollbar
     * handle is in a dragging state it will emit an event with the new scrollTop.
     */
    mouseMove(event) {
      if (this.dragging === 'vertical') {
        event.preventDefault()
        const element = this.$parent[this.vertical]()
        const delta = event.clientY - this.mouseStart
        const pixel = element.scrollHeight / element.clientHeight
        const top = Math.ceil((this.elementStart + delta) * pixel)

        this.$emit('vertical', top)
        this.updateVertical()
      }

      if (this.dragging === 'horizontal') {
        event.preventDefault()
        const element = this.$parent[this.horizontal]()
        const delta = event.clientX - this.mouseStart
        const pixel = element.scrollWidth / element.clientWidth
        const left = Math.ceil((this.elementStart + delta) * pixel)

        this.$emit('horizontal', left)
        this.updateHorizontal()
      }
    },
    /**
     * Event that is called when the mouse button is released. It will stop the dragging
     * of the handle.
     */
    mouseUp() {
      if (this.dragging === null) {
        return
      }

      this.dragging = null
      this.elementStart = 0
      this.mouseStart = 0
    },
  },
}
</script>
