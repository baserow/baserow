import MoveToBody from '@baserow/modules/core/mixins/moveToBody'

export default {
  mixins: [MoveToBody],
  data() {
    return {
      open: false,
      // Firefox and Chrome both can both have a different `target` element on `click`
      // when you release the mouse at different coordinates. Therefore we expect this
      // variable to be set on mousedown to be consistent.
      downElement: null,
      isModal: true,
    }
  },
  props: {
    canClose: {
      type: Boolean,
      default: true,
      required: false,
      mouseDownEvent: null,
    },
  },
  mounted() {
    this.$bus.$on('close-modals', this.hide)
  },
  beforeDestroy() {
    this.$bus.$off('close-modals', this.hide)
  },
  destroyed() {
    window.removeEventListener('keyup', this.keyup)
  },
  methods: {
    /**
     * Toggle the open state of the modal.
     */
    toggle(value) {
      if (value === undefined) {
        value = !this.open
      }

      if (value) {
        this.show()
      } else {
        this.hide()
      }
    },
    /**
     * Returns if the modal is open or not.
     */
    isOpen() {
      return this.open
    },
    /**
     * Show the modal.
     */
    show() {
      this.open = true
      this.$emit('show')
      window.addEventListener('keyup', this.keyup)
      document.body.classList.add('prevent-scroll')
      const mouseDownEvent = (event) => {
        this.downElement = event.target
      }
      document.body.addEventListener('mousedown', mouseDownEvent)

      // store the handler for later removal
      this.mouseDownEvent = mouseDownEvent
    },
    /**
     * Hide the modal.
     */
    hide(emit = true) {
      console.log('should hide')
      if (!this.open) {
        return
      }

      const hasOpenModalAsChild = this.moveToBody.children.some((child) => {
        return child.isModal === true && child.open === true
      })
      // When the `esc` key is pressed and multiple modals are open, then we don't
      // want to close them all. Only last opened modal should close. This will make
      // sure that if there is an open child modal, it will not hide the parent modal.
      if (hasOpenModalAsChild) {
        return
      }

      this.$nextTick(() => (this.open = false))

      // cleanup
      if (this.mouseDownEvent) {
        document.body.removeEventListener('mousedown', this.mouseDownEvent)
        this.mouseDownEvent = null
      }
      document.body.classList.remove('prevent-scroll')
      window.removeEventListener('keyup', this.keyup)

      if (emit) {
        this.$emit('hidden')
      }
    },
    /**
     * If someone actually clicked on the modal wrapper and not one of his children the
     * modal should be closed.
     */
    outside() {
      if (this.downElement === this.$refs.modalWrapper && this.canClose) {
        this.hide()
      }
    },
    /**
     * When the escape key is pressed the modal needs to be hidden.
     */
    keyup(event) {
      if (event.key === 'Escape' && this.canClose) {
        this.hide()
      }
    },
  },
}
