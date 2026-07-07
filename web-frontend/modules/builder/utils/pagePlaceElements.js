import {
  PAGE_ELEMENT_BEHAVIOURS,
  PAGE_PLACES,
} from '@baserow/modules/builder/enums'

/**
 * Groups elements by page place while keeping the source element untouched.
 * `isFixed` is derived here so renderers can split a place into fixed and
 * normal flows without mutating store/API element objects.
 *
 * @param {Array} elements
 * @param {Object} registry
 * @param {Array<string>} places
 * @returns {Array<{
 *   place: string,
 *   elements: Array<{
 *     element: Object,
 *     isFixed: boolean
 *   }>
 * }>}
 */
export function groupElementsByPagePlace(
  elements,
  registry,
  places = Object.values(PAGE_PLACES)
) {
  const elementEntries = elements
    .map((element) => ({
      place: registry.get('element', element.type).getPagePlace(),
      element,
      isFixed: element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED,
    }))
    .filter(({ place }) => places.includes(place))

  return places.map((place) => ({
    place,
    elements: elementEntries
      .filter((elementEntry) => elementEntry.place === place)
      .map(({ element, isFixed }) => ({ element, isFixed })),
  }))
}
