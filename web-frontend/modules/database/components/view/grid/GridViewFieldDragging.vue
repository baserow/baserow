<template>
  <div v-show="dragging && moved">
    <div
      class="grid-view__field-dragging"
      :style="{ width: draggingWidth + 'px', left: draggingLeft + 'px' }"
    ></div>
    <div
      class="grid-view__field-target"
      :style="{ left: targetLeft + 'px' }"
    ></div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

export default {
  name: 'GridViewFieldDragging',
  mixins: [gridViewHelpers],
  props: {
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    offset: {
      type: Number,
      required: false,
      default: 0,
    },
    containerWidth: {
      type: Number,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      // Indicates if the user is dragging a field to another position.
      dragging: false,
      // Indicates whether the user has moved the mouse more than the 3px threshold.
      moved: false,
      // The field object that is being dragged.
      field: null,
      // The id of the field where the dragged field must be placed after.
      targetFieldId: null,
      // The horizontal starting position of the mouse.
      mouseStartX: 0,
      // The vertical starting position of the mouse.
      mouseStartY: 0,
      // The horizontal scrollbar offset starting position.
      scrollStart: 0,
      // The width of the dragging animation, this is equal to the width of the field.
      draggingWidth: 0,
      // The position of the dragging animation.
      draggingLeft: 0,
      // The position of the target indicator where the field is going to be moved to.
      targetLeft: 0,
      // The mouse move event.
      lastMoveEvent: null,
      // Indicates if the user is auto scrolling at the moment.
      autoScrolling: false,
    }
  },
  beforeDestroy() {
    this.cancel()
  },
  methods: {
    getFieldLeft(id) {
      let left = 0
      for (let i = 0; i < this.fields.length; i++) {
        if (this.fields[i].id === id) {
          break
        }
        left += this.getFieldWidth(this.fields[i])
      }
      return left
    },
    /**
     * Called when the field dragging must start. It will register the global mouse
     * move, mouse up events and keyup events so that the user can drag the field to
     * the correct position.
     */
    start(field, event) {
      this.field = field
      this.targetFieldId = field.id
      this.dragging = true
      this.moved = false
      this.mouseStartX = event.clientX
      this.mouseStartY = event.clientY
      this.scrollStart = this.$parent.$el.scrollLeft
      this.draggingLeft = 0
      this.targetLeft = 0

      this.$el.moveEvent = (event) => this.move(event)
      window.addEventListener('mousemove', this.$el.moveEvent)

      this.$el.upEvent = (event) => this.up(event)
      window.addEventListener('mouseup', this.$el.upEvent)

      this.$el.keydownEvent = (event) => {
        if (event.key === 'Escape') {
          // When the user presses the escape key we want to cancel the action
          this.cancel(event)
        }
      }
      document.body.addEventListener('keydown', this.$el.keydownEvent)
    },
    /**
     * The move method is called when every time the user moves the mouse while
     * dragging a field. It can also be called while auto scrolling.
     */
    move(event = null, startAutoScroll = true) {
      if (event !== null) {
        event.preventDefault()
        this.lastMoveEvent = event
      } else {
        event = this.lastMoveEvent
      }

      // Sometimes the user could accidentally drag the element one or two pixels while
      // clicking it. Because it could be annoying that the click doesn't work because
      // the moving state started, we check here if the user has at least dragged
      // the element 3 pixels vertically or horizontally before starting the moved
      // state.
      if (!this.moved) {
        if (
          Math.abs(event.clientX - this.mouseStartX) > 3 ||
          Math.abs(event.clientY - this.mouseStartY) > 3
        ) {
          this.moved = true
        } else {
          return
        }
      }

      // This is the horizontally scrollable element.
      const element = this.$parent.$el

      this.draggingWidth = this.getFieldWidth(this.field)

      // Calculate the left position of the dragging animation. This is the transparent
      // overlay that has the same width as the field.
      this.draggingLeft =
        this.offset +
        Math.min(
          this.getFieldLeft(this.field.id) +
            event.clientX -
            this.mouseStartX +
            this.$parent.$el.scrollLeft -
            this.scrollStart,
          this.containerWidth - this.draggingWidth
        )

      // Calculate which after which field we want to place the field that is currently
      // being dragged. This is named the target. We also calculate what position the
      // field would have for visualisation purposes.
      const mouseLeft =
        event.clientX -
        element.getBoundingClientRect().left +
        element.scrollLeft
      let left = this.offset
      for (let i = 0; i < this.fields.length; i++) {
        const width = this.getFieldWidth(this.fields[i])
        const nextWidth =
          i + 1 < this.fields.length
            ? this.getFieldWidth(this.fields[i + 1])
            : width
        const leftHalf = left + Math.floor(width / 2)
        const rightHalf = left + width + Math.floor(nextWidth / 2)
        if (i === 0 && mouseLeft < leftHalf) {
          this.targetFieldId = 0
          // The value 1 makes sure it is visible instead of falling outside of the
          // view port.
          this.targetLeft = Math.max(this.offset, 1)
          break
        }
        if (mouseLeft > leftHalf && mouseLeft < rightHalf) {
          this.targetFieldId = this.fields[i].id
          this.targetLeft = left + width
          break
        }
        left += width
      }

      // If the user is not already auto scrolling, which happens while dragging and
      // moving the element outside of the view port at the left or right side, we
      // might need to initiate that process.
      if (!this.autoScrolling || !startAutoScroll) {
        const relativeLeft = this.draggingLeft - element.scrollLeft
        const relativeRight = relativeLeft + this.getFieldWidth(this.field)
        const maxScrollLeft = element.scrollWidth - element.clientWidth
        let speed = 0

        if (relativeLeft < 0 && element.scrollLeft > 0) {
          // If the dragging animation falls out of the left side of the viewport we
          // need to auto scroll to the left.
          speed = -Math.ceil(Math.min(Math.abs(relativeLeft), 100) / 20)
        } else if (
          relativeRight > element.clientWidth &&
          element.scrollLeft < maxScrollLeft
        ) {
          // If the dragging animation falls out of the right side of the viewport we
          // need to auto scroll to the right.
          speed = Math.ceil(
            Math.min(relativeRight - element.clientWidth, 100) / 20
          )
        }

        // If the speed is either a position or negative, so not 0, we know that we
        // need to start auto scrolling.
        if (speed !== 0) {
          this.autoScrolling = true
          this.$emit('scroll', { pixelY: 0, pixelX: speed })
          this.$el.scrollTimeout = setTimeout(() => {
            this.move(null, false)
          }, 1)
        } else {
          this.autoScrolling = false
        }
      }
    },
    /**
     * Can be called when the current dragging state needs to be stopped. It will
     * remove all the created event listeners and timeouts.
     */
    cancel() {
      this.dragging = false
      this.mouseStartX = 0
      this.mouseStartY = 0
      window.removeEventListener('mousemove', this.$el.moveEvent)
      window.removeEventListener('mouseup', this.$el.upEvent)
      document.body.addEventListener('keydown', this.$el.keydownEvent)
      clearTimeout(this.$el.scrollTimeout)
    },
    /**
     * Called when the user releases the mouse on a the desired position. It will
     * calculate the new position of the field in the list and if it has changed
     * position, then the order in the field options is updated accordingly.
     */
    async up(event) {
      event.preventDefault()
      this.cancel()

      if (!this.moved) {
        return
      }

      // We don't need to do anything if the field needs to be placed after itself
      // because that wouldn't change the position.
      if (this.field.id === this.targetFieldId) {
        return
      }

      // If targetfieldId is 0 then the field should be moved to the left of the
      // first field, otherwise it should be moved at the right of the target field
      const position = this.targetFieldId === 0 ? 'left' : 'right'
      const fromField = {
        id: this.targetFieldId === 0 ? this.fields[0].id : this.targetFieldId,
      }
      try {
        await this.$store.dispatch(
          `${this.storePrefix}view/grid/updateSingleFieldOptionOrder`,
          {
            fieldToMove: this.field,
            position,
            fromField,
            readOnly: this.readOnly,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
