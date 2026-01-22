import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * This mixin can be used in combination with a view component that uses the
 * bufferedRows store mixin. It allows for drag and drop ordering of the items. It
 * can be used by adding the following listeners to the row objects.
 *
 * @mousedown="rowDown($event, row)"
 * @mousemove="rowMoveOver($event, row)"
 * @mouseenter="rowMoveOver($event, row)"
 *
 * Note that the parent component must implement the `getDragAndDropStoreName` method.
 */
export default {
  data() {
    return {
      // Must be overwritten by the parent component. It should hold the class name
      // of the clone of the dom element when the user starts dragging the row.
      dragAndDropCloneClass: '',
      // Indicates whether a transition effect is currently active.
      dragAndDropTransitioning: false,
      // The row object that the user clicked on.
      dragAndDropDownRow: null,
      // The initial horizontal position absolute client position of the card after
      // mousedown.
      dragAndDropRowClientX: 0,
      // The initial vertical position absolute client position of the card after
      // mousedown.
      dragAndDropRowClientY: 0,
      // Event handler references for cleanup
      mouseUpEvent: null,
      keydownEvent: null,
      mouseMoveEvent: null,
      // Cloned elements for drag visual feedback
      clonedElement: null,
      clonedWrapper: null,
      // Position offsets for dragged element
      dragAndDropDownRowTop: 0,
      dragAndDropDownRowLeft: 0,
    }
  },
  computed: {
    dragAndDropDraggingRow() {
      return this.$store.getters[
        `${this.getDragAndDropStoreName(this)}/getDraggingRow`
      ]
    },
  },
  methods: {
    /**
     * Should return the name of the store that's has the bufferedRows mixed in.
     * This can be different for each component, to this method must be overwritten.
     */
    getDragAndDropStoreName(props) {
      throw new Error(
        'The `getDragAndDropStoreName` method must be implemented.'
      )
    },
    /**
     * Called when a user presses the left mouse on a card. This method will prepare
     * the dragging if the user moves the mouse a bit. Otherwise, if the mouse is
     * release without moving, the edit modal is opened.
     */
    rowDown(event, row, readOnly = false) {
      // If it isn't a left click.
      if (event.button !== 0 || !row) {
        return
      }

      event.preventDefault()

      this.dragAndDropDownRow = row

      this.mouseUpEvent = (event) => this.rowUp(event)
      window.addEventListener('mouseup', this.mouseUpEvent)

      if (!readOnly) {
        const rect = event.target.getBoundingClientRect()
        this.dragAndDropRowClientX = event.clientX
        this.dragAndDropRowClientY = event.clientY
        this.dragAndDropDownRowTop = event.clientY - rect.top
        this.dragAndDropDownRowLeft = event.clientX - rect.left

        this.clonedElement = document.createElement('div')
        this.clonedElement.innerHTML = event.target.outerHTML
        this.clonedElement.style = `position: absolute; left: 0; top: 0; width: ${rect.width}px; z-index: 10; pointer-events: none;`
        this.clonedElement.firstChild.classList.add(this.dragAndDropCloneClass)

        this.clonedWrapper = document.createElement('div')
        this.clonedWrapper.style =
          'position: absolute; left: 0; top: 0; right: 0; bottom: 0; overflow: hidden; pointer-events: none;'
        this.clonedWrapper.appendChild(this.clonedElement)

        this.keydownEvent = (event) => {
          if (event.key === 'Escape') {
            if (this.dragAndDropDraggingRow !== null) {
              this.$store.dispatch(
                `${this.getDragAndDropStoreName(this)}/cancelRowDrag`,
                {
                  view: this.view,
                  fields: this.fields,
                  row: this.dragAndDropDraggingRow,
                }
              )
            }
            this.rowCancel(event)
          }
        }
        document.body.addEventListener('keydown', this.keydownEvent)

        this.mouseMoveEvent = (event) => this.rowMove(event)
        window.addEventListener('mousemove', this.mouseMoveEvent)

        this.rowMove(event)
      }
    },
    /**
     * Called when moving the mouse after the down event on a row. If we're not in a
     * dragging state already, it must be started if the user moves more than 3 pixels.
     */
    async rowMove(event) {
      if (
        this.dragAndDropDraggingRow === null &&
        // We only want to allow ordering by drag and drop if there aren't any
        // sortings because if there are, the ordering is not only based of the
        // `order` property and drag and dropping in the right position doesn't make
        // sense.
        this.view.sortings.length === 0
      ) {
        if (
          Math.abs(event.clientX - this.dragAndDropRowClientX) > 3 ||
          Math.abs(event.clientY - this.dragAndDropRowClientY) > 3
        ) {
          document.body.appendChild(this.clonedWrapper)
          await this.$store.dispatch(
            `${this.getDragAndDropStoreName(this)}/startRowDrag`,
            {
              row: this.dragAndDropDownRow,
            }
          )
        }
      }

      this.clonedElement.style.top =
        event.clientY - this.dragAndDropDownRowTop + 'px'
      this.clonedElement.style.left =
        event.clientX - this.dragAndDropDownRowLeft + 'px'
    },
    /**
     * Called when the user release the mouse after pressing the left mouse button
     * on the row. It will check if we're in a dragging state and if so, we need to
     * stop the dragging of the row and make the new position persistent.
     */
    async rowUp() {
      if (this.dragAndDropDraggingRow !== null) {
        this.rowCancel()

        try {
          await this.$store.dispatch(
            `${this.getDragAndDropStoreName(this)}/stopRowDrag`,
            {
              table: this.table,
              view: this.view,
              fields: this.fields,
              primary: this.primary,
            }
          )
        } catch (error) {
          notifyIf(error)
        }
      } else {
        // Call the `rowClick` method because in some cases, we might want to take
        // certain action after a "normal" click on the row. Like for example
        // opening a row edit modal.
        this.rowClick(this.dragAndDropDownRow)
        this.rowCancel()
      }
    },
    rowCancel() {
      this.dragAndDropDownRow = null
      // If the view is read only, the clonedWrapper is never created.
      if (this.clonedWrapper) {
        this.clonedWrapper.remove()
        this.clonedWrapper = null
        this.clonedElement = null
      }
      document.body.removeEventListener('keydown', this.keydownEvent)
      window.removeEventListener('mousemove', this.mouseMoveEvent)
      window.removeEventListener('mouseup', this.mouseUpEvent)
      this.keydownEvent = null
      this.mouseMoveEvent = null
      this.mouseUpEvent = null
    },
    /**
     * Must be called when the user hovers over another row. It will check if we're
     * currently in a dragging state and if so, the row is temporarily moved to the
     * new position.
     */
    async rowMoveOver(event, row) {
      if (
        row === null ||
        this.dragAndDropDraggingRow === null ||
        this.dragAndDropDraggingRow.id === row.id ||
        this.dragAndDropTransitioning
      ) {
        return
      }

      const moved = await this.$store.dispatch(
        `${this.getDragAndDropStoreName(this)}/forceMoveRowBefore`,
        {
          row: this.dragAndDropDraggingRow,
          targetRow: row,
        }
      )
      if (moved) {
        this.rowMoved()
      }
    },
    /**
     * After a row has been moved, we need to temporarily need to set the transition
     * state to true. While it's true, it can't be moved to another position to avoid
     * strange transition effects of other cards.
     */
    rowMoved() {
      this.dragAndDropTransitioning = true
      setTimeout(
        () => {
          this.dragAndDropTransitioning = false
        },
        // Must be kept in sync with the transition-duration of
        // gallery.scss.gallery-view__cards--dragging
        100 + 1
      )
    },
    /**
     * Is called when the user clicks on a row without moving it to another position.
     */
    rowClick() {},
  },
}
