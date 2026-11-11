import { defineComponent } from 'vue'

/**
 * Stands in for `Modal`, rendering its content only while it's shown.
 */
export const ModalStub = defineComponent({
  name: 'Modal',
  emits: ['show', 'hidden'],
  data: () => ({ open: false }),
  methods: {
    show() {
      this.open = true
      this.$emit('show')
    },
    hide() {
      this.open = false
      this.$emit('hidden')
    },
  },
  template: '<div v-if="open"><slot /></div>',
})
