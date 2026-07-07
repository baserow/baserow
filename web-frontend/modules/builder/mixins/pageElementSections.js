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
    selectedPreviewClassName: 'page__header--element-selected',
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
    selectedPreviewClassName: 'page__content--element-selected',
  },
  {
    key: 'footer',
    place: PAGE_PLACES.FOOTER,
    isFixed: false,
    tag: 'footer',
    classNames: ['page__footer'],
    selectedPreviewClassName: 'page__footer--element-selected',
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
        elements: this.getElementsForSection(section),
      }))
    },
    visiblePageElementSections() {
      return this.pageElementSections.filter(
        (section) => section.elements.length !== 0
      )
    },
  },
  methods: {
    getElementsForSection(section) {
      if (section.place === PAGE_PLACES.CONTENT) {
        return this.elements || []
      }

      return this.getEntriesForSharedPlace(section.place)
        .filter((entry) => entry.isFixed === section.isFixed)
        .map((entry) => entry.element)
    },
    getEntriesForSharedPlace(place) {
      return (
        this.sharedElementsByPlace.find((group) => group.place === place)
          ?.elements || []
      )
    },
  },
}
