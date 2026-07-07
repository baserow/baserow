import { PAGE_PLACES } from '@baserow/modules/builder/enums'
import { groupElementsByPagePlace } from '@baserow/modules/builder/utils/pagePlaceElements'

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
    sharedElementsByPlace() {
      return groupElementsByPagePlace(this.sharedElements, this.$registry)
    },
    pageElementSections() {
      return PAGE_ELEMENT_SECTION_CONFIGS.map((section) => ({
        ...section,
        elements: this.getPageSectionElements(section),
      }))
    },
    visiblePageElementSections() {
      return this.pageElementSections.filter(
        (section) => section.elements.length !== 0
      )
    },
    headerElementsSection() {
      return this.getSharedElementSection(PAGE_PLACES.HEADER)
    },
    footerElementsSection() {
      return this.getSharedElementSection(PAGE_PLACES.FOOTER)
    },
    fixedHeaderElements() {
      return this.getSharedElementsForPlace(PAGE_PLACES.HEADER, true)
    },
    normalHeaderElements() {
      return this.getSharedElementsForPlace(PAGE_PLACES.HEADER, false)
    },
    fixedFooterElements() {
      return this.getSharedElementsForPlace(PAGE_PLACES.FOOTER, true)
    },
    normalFooterElements() {
      return this.getSharedElementsForPlace(PAGE_PLACES.FOOTER, false)
    },
  },
  methods: {
    getSharedElementSection(place) {
      return (
        this.sharedElementsByPlace.find((section) => section.place === place) || {
          place,
          elements: [],
        }
      )
    },
    getPageSectionElements(section) {
      if (section.place === PAGE_PLACES.CONTENT) {
        return this.elements || []
      }
      return this.getSharedElementsForPlace(section.place, section.isFixed)
    },
    getSharedElementsForPlace(place, isFixed) {
      return this.getElementsMatchingFixedState(
        this.getSharedElementSection(place),
        isFixed
      )
    },
    getElementsMatchingFixedState(section, isFixed) {
      return section.elements
        .filter((elementEntry) => elementEntry.isFixed === isFixed)
        .map((elementEntry) => elementEntry.element)
    },
  },
}
