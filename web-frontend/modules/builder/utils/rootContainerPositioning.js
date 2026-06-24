import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

const MULTI_PAGE_CONTAINER_TYPES = ['header', 'footer']

function isRootSimpleContainer(element) {
  return element.type === 'simple_container' && !element.parent_element_id
}

function isRootMultiPageContainer(element) {
  return (
    MULTI_PAGE_CONTAINER_TYPES.includes(element.type) &&
    !element.parent_element_id
  )
}

function getPositioningAlignment(element) {
  if (element.type === 'header') {
    return PAGE_ELEMENT_ALIGNMENTS.TOP
  }

  if (element.type === 'footer') {
    return PAGE_ELEMENT_ALIGNMENTS.BOTTOM
  }

  return element.alignment || PAGE_ELEMENT_ALIGNMENTS.TOP
}

function hasPositioningBehaviour(element) {
  if (isRootSimpleContainer(element)) {
    return [
      PAGE_ELEMENT_BEHAVIOURS.STICKY,
      PAGE_ELEMENT_BEHAVIOURS.FIXED,
    ].includes(element.behaviour)
  }

  return (
    isRootMultiPageContainer(element) &&
    element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED
  )
}

// Root-level simple and multi-page containers can opt into page-level positioning.
export function isPositionedRootContainer(element) {
  return (
    hasPositioningBehaviour(element) &&
    [PAGE_ELEMENT_ALIGNMENTS.TOP, PAGE_ELEMENT_ALIGNMENTS.BOTTOM].includes(
      getPositioningAlignment(element)
    )
  )
}

// Fixed root containers are rendered in a separate preview overlay to stay viewport-aligned.
export function isFixedRootContainer(element) {
  return (
    isPositionedRootContainer(element) &&
    element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED
  )
}

// Returns the CSS classes that apply the chosen behaviour and top/bottom alignment.
export function getRootContainerPositioningClasses(element) {
  if (!isPositionedRootContainer(element)) {
    return {}
  }

  const behaviour = element.behaviour
  const alignment = getPositioningAlignment(element)

  return {
    'element--positioned': true,
    [`element--position-${behaviour}`]: true,
    [`element--position-alignment-${alignment}`]: true,
  }
}
