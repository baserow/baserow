import { PAGE_PLACES } from '@baserow/modules/builder/enums'
import { getElementsPerPlace } from '@baserow/modules/builder/utils/pagePlaceElements'

const PAGE_ELEMENT_SECTION_CONFIGS = [
  {
    key: 'fixed-header',
    place: PAGE_PLACES.HEADER,
    isFixed: true,
    tag: 'div',
    classNames: ['page__fixed-stack', 'page__fixed-stack--top'],
    previewClassNames: ['page__fixed-stack--header'],
    separator: {
      label: 'pagePreview.fixedHeader',
      position: 'after',
      insideSection: true,
    },
  },
  {
    key: 'header',
    place: PAGE_PLACES.HEADER,
    isFixed: false,
    tag: 'header',
    classNames: ['page__header'],
    selectedClassName: 'page__header--element-selected',
    separator: {
      label: 'pagePreview.header',
      position: 'after',
    },
  },
  {
    key: 'content',
    place: PAGE_PLACES.CONTENT,
    tag: 'div',
    classNames: ['page__content'],
    selectedClassName: 'page__content--element-selected',
  },
  {
    key: 'footer',
    place: PAGE_PLACES.FOOTER,
    isFixed: false,
    tag: 'footer',
    classNames: ['page__footer'],
    selectedClassName: 'page__footer--element-selected',
    separator: {
      label: 'pagePreview.footer',
      position: 'before',
    },
  },
  {
    key: 'fixed-footer',
    place: PAGE_PLACES.FOOTER,
    isFixed: true,
    tag: 'div',
    classNames: ['page__fixed-stack', 'page__fixed-stack--bottom'],
    previewClassNames: ['page__fixed-stack--footer'],
    separator: {
      label: 'pagePreview.fixedFooter',
      position: 'before',
      insideSection: true,
    },
  },
]

export default {
  computed: {
    elementsPerPlace() {
      return getElementsPerPlace(this.sharedElements, this.$registry)
    },
    pageElementSections() {
      return PAGE_ELEMENT_SECTION_CONFIGS.map((section) => ({
        ...section,
        elements: this.getElementsForSection(section),
      }))
    },
    visiblePageElementSections() {
      return this.pageElementSections.filter(
        (section) => section.elements.length !== 0
      )
    },
    headerElementsSection() {
      return this.getElementsSection(PAGE_PLACES.HEADER)
    },
    footerElementsSection() {
      return this.getElementsSection(PAGE_PLACES.FOOTER)
    },
    fixedHeaderElements() {
      return this.getElementsByPlace(PAGE_PLACES.HEADER, true)
    },
    normalHeaderElements() {
      return this.getElementsByPlace(PAGE_PLACES.HEADER, false)
    },
    fixedFooterElements() {
      return this.getElementsByPlace(PAGE_PLACES.FOOTER, true)
    },
    normalFooterElements() {
      return this.getElementsByPlace(PAGE_PLACES.FOOTER, false)
    },
  },
  methods: {
    getElementsSection(place) {
      return (
        this.elementsPerPlace.find((section) => section.place === place) || {
          place,
          elements: [],
        }
      )
    },
    getElementsForSection(section) {
      if (section.place === PAGE_PLACES.CONTENT) {
        return this.elements || []
      }
      return this.getElementsByPlace(section.place, section.isFixed)
    },
    getElementsByPlace(place, isFixed) {
      return this.getElementsByFixedState(this.getElementsSection(place), isFixed)
    },
    getElementsByFixedState(section, isFixed) {
      return section.elements
        .filter((elementEntry) => elementEntry.isFixed === isFixed)
        .map((elementEntry) => elementEntry.element)
    },
  },
}
