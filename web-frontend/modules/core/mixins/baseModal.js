import MoveToBody from '@baserow/modules/core/mixins/moveToBody'
import { v4 as uuidv4 } from 'uuid'

export default {
  mixins: [MoveToBody],
  data() {
    return {
      open: false,
      // Firefox and Chrome both can both have a different `target` element on `click`
      // when you release the mouse at different coordinates. Therefore we expect this
      // variable to be set on mousedown to be consistent.
      downElement: null,
      modalId: `modal_${uuidv4()}`,
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
    this.popFromModalStack()
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
      if (this.open) {
        return
      }

      this.open = true
      this.$emit('show')

      this.pushToModalStack()

      document.body.classList.add('prevent-scroll')
      const mouseDownEvent = (event) => {
        this.downElement = event.target
      }
      document.body.addEventListener('mousedown', mouseDownEvent)

      this.$once('hidden', () => {
        document.body.removeEventListener('mousedown', mouseDownEvent)
        document.body.classList.remove('prevent-scroll')
        this.popFromModalStack()
      })
    },
    /**
     * Push the modal to the stack and register the close event.
     */
    pushToModalStack() {
      this.$store.dispatch('modal/pushModal', {
        id: this.modalId,
        canClose: this.canClose,
      })

      this.$bus.$on(`modal:close:${this.modalId}`, this.hide)
    },
    /**
     * Pop the modal from the stack and unregister the close event.
     */
    popFromModalStack() {
      this.$bus.$off(`modal:close:${this.modalId}`, this.hide)
      this.$store.dispatch('modal/popModal', this.modalId)
    },
    /**
     * Hide the modal.
     */
    hide(emit = true) {
      if (!this.open) {
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
  },
}
