import { PAGE_ALIGNMENT_BEHAVIOURS, PAGE_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    pageAlignmentClass() {
      const isSticky = this.element.behaviour === PAGE_ALIGNMENT_BEHAVIOURS.STICKY ? '--sticky' : ''
      return Object.values(PAGE_ALIGNMENTS).includes(this.element.alignment)
        ? `positioned-container-element__page-alignment-${this.element.alignment}${isSticky}`
        : ''
    },
  },
  methods: {
    isPositionedContainer() {
      return this.element.type === 'positioned_container'
    },
  },
}
