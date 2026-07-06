import { PAGE_PLACES } from '@baserow/modules/builder/enums'
import { getElementsPerPlace } from '@baserow/modules/builder/utils/pagePlaceElements'

export default {
  computed: {
    elementsPerPlace() {
      return getElementsPerPlace(this.sharedElements, this.$registry)
    },
    headerElementsSection() {
      return this.elementsPerPlace.find(
        (section) => section.place === PAGE_PLACES.HEADER
      )
    },
    footerElementsSection() {
      return this.elementsPerPlace.find(
        (section) => section.place === PAGE_PLACES.FOOTER
      )
    },
    fixedHeaderElements() {
      return this.getElementsForBehaviour(this.headerElementsSection, true)
    },
    normalHeaderElements() {
      return this.getElementsForBehaviour(this.headerElementsSection, false)
    },
    fixedFooterElements() {
      return this.getElementsForBehaviour(this.footerElementsSection, true)
    },
    normalFooterElements() {
      return this.getElementsForBehaviour(this.footerElementsSection, false)
    },
  },
  methods: {
    getElementsForBehaviour(section, isFixed) {
      return section.elements
        .filter((elementEntry) => elementEntry.isFixed === isFixed)
        .map((elementEntry) => elementEntry.element)
    },
  },
}
