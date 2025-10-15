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

      this.$once('hidden', () => {
        document.body.removeEventListener('mousedown', mouseDownEvent)
        document.body.classList.remove('prevent-scroll')
        window.removeEventListener('keyup', this.keyup)
      })
    },
    /**
     * Hide the modal.
     */
    hide(emit = true) {
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

      // This is a temporary fix. What happens is the modal is opened by a context menu
      // item and the user closes the modal, the element is first deleted and then the
      // click outside event of the context is fired. It then checks if the click was
      // inside one of his children, but because the modal element doesn't exists
      // anymore it thinks it was outside, so is closes the context menu which we don't
      // want automatically.
      setTimeout(() => {
        this.open = false
      })

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
