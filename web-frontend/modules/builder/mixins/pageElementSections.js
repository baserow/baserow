import {
  PAGE_ELEMENT_BEHAVIOURS,
  PAGE_PLACES,
} from '@baserow/modules/builder/enums'

const PAGE_ELEMENT_SECTION_CONFIGS = [
  {
    key: 'fixed-header',
    place: PAGE_PLACES.HEADER,
    isFixed: true,
    tag: 'div',
    classNames: ['page__fixed-stack', 'page__fixed-stack--top'],
    previewClassNames: ['page__fixed-stack--header'],
    selectedPreviewClassName: 'page__fixed-stack--element-selected',
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
    selectedPreviewClassName: 'page__fixed-stack--element-selected',
    separator: {
      label: 'pagePreview.fixedFooter',
      position: 'before',
      insideSection: true,
    },
  },
]

function groupElementsByPagePlace(
  elements,
  registry,
  places = Object.values(PAGE_PLACES)
) {
  const elementsWithPlace = elements
    .map((element) => ({
      place: registry.get('element', element.type).getPagePlace(),
      element,
    }))
    .filter(({ place }) => places.includes(place))

  return places.map((place) => ({
    place,
    elements: elementsWithPlace
      .filter((elementWithPlace) => elementWithPlace.place === place)
      .map(({ element }) => element),
  }))
}

export default {
  computed: {
    pageElementSections() {
      const elementsByPlace = groupElementsByPagePlace(
        [...(this.sharedElements || []), ...(this.elements || [])],
        this.$registry
      )

      return PAGE_ELEMENT_SECTION_CONFIGS.map((section) => ({
        ...section,
        elements: this.getElementsForSection(section, elementsByPlace),
      }))
    },
    visiblePageElementSections() {
      return this.pageElementSections.filter(
        (section) => section.elements.length !== 0
      )
    },
  },
  methods: {
    getElementsForSection(section, elementsByPlace) {
      const elementsForPlace =
        elementsByPlace.find((group) => group.place === section.place)
          ?.elements || []

      if (section.isFixed === undefined) {
        return elementsForPlace
      }

      return elementsForPlace.filter(
        (element) =>
          (element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED) ===
          section.isFixed
      )
    },
  },
}
