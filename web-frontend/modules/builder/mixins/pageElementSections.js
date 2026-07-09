import { PAGE_PLACES } from '@baserow/modules/builder/enums'

const PAGE_ELEMENT_SECTION_CONFIGS = [
  {
    key: 'fixed-header',
    place: PAGE_PLACES.HEADER,
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

function groupElementsBySection(
  elements,
  registry,
  sections = PAGE_ELEMENT_SECTION_CONFIGS.map(({ key }) => key)
) {
  const elementsWithSection = elements
    .map((element) => ({
      section: registry.get('element', element.type).getPageSection(element),
      element,
    }))
    .filter(({ section }) => sections.includes(section))

  return sections.map((section) => ({
    section,
    elements: elementsWithSection
      .filter((elementWithSection) => elementWithSection.section === section)
      .map(({ element }) => element),
  }))
}

export default {
  computed: {
    pageElementSections() {
      const elementsBySection = groupElementsBySection(
        [...(this.sharedElements || []), ...(this.elements || [])],
        this.$registry
      )

      return PAGE_ELEMENT_SECTION_CONFIGS.map((section) => ({
        ...section,
        elements: this.getElementsForSection(section, elementsBySection),
      }))
    },
    visiblePageElementSections() {
      return this.pageElementSections.filter(
        (section) => section.elements.length !== 0
      )
    },
  },
  methods: {
    getElementsForSection(section, elementsBySection) {
      return (
        elementsBySection.find((group) => group.section === section.key)
          ?.elements || []
      )
    },
  },
}
