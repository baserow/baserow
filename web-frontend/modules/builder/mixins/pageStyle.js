import { PAGE_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    pageAlignmentClass() {
      return Object.values(PAGE_ALIGNMENTS).includes(this.element.alignment)
        ? `positioned-container-element__page-alignment-${this.element.alignment}`
        : ''
    },
  },
  methods: {
    isPositionedContainer() {
      return this.element.type === 'positioned_container'
    },
  },
}
