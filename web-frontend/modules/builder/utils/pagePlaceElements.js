import {
  PAGE_ELEMENT_BEHAVIOURS,
  PAGE_PLACES,
} from '@baserow/modules/builder/enums'

/**
 * Groups elements by their registered page place and splits each group by
 * behaviour. The optional places list controls which sections are returned.
 *
 * @param {Array} elements
 * @param {Object} registry
 * @param {Array<string>} places
 * @returns {Array<{
 *   place: string,
 *   hasElements: boolean,
 *   fixedElements: Array,
 *   normalElements: Array
 * }>}
 */
export function getElementsPerPlace(
  elements,
  registry,
  places = Object.values(PAGE_PLACES)
) {
  const elementsPerPlace = places.map((place) => ({
    place,
    hasElements: false,
    fixedElements: [],
    normalElements: [],
  }))
  const elementsPerPlaceByPlace = elementsPerPlace.reduce((acc, section) => {
    acc[section.place] = section
    return acc
  }, {})

  elements.forEach((element) => {
    const place = registry.get('element', element.type).getPagePlace()
    const section = elementsPerPlaceByPlace[place]

    if (!section) {
      return
    }

    section.hasElements = true

    if (element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED) {
      section.fixedElements.push(element)
    } else {
      section.normalElements.push(element)
    }
  })

  return elementsPerPlace
}
