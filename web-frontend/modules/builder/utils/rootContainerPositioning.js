import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

const MULTI_PAGE_CONTAINER_TYPES = ['header', 'footer']

export function isRootSimpleContainer(element) {
  return element.type === 'simple_container' && !element.parent_element_id
}

export function isRootMultiPageContainer(element) {
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
  return (
    isRootSimpleContainer(element) &&
    [PAGE_ELEMENT_BEHAVIOURS.STICKY, PAGE_ELEMENT_BEHAVIOURS.FIXED].includes(
      element.behaviour
    )
  )
}

// Root-level simple containers can opt into page-level positioning.
export function isPositionedRootContainer(element) {
  return (
    hasPositioningBehaviour(element) &&
    [PAGE_ELEMENT_ALIGNMENTS.TOP, PAGE_ELEMENT_ALIGNMENTS.BOTTOM].includes(
      getPositioningAlignment(element)
    )
  )
}

// Fixed root simple containers are rendered in a separate preview overlay to stay viewport-aligned.
export function isFixedRootSimpleContainer(element) {
  return (
    isPositionedRootContainer(element) &&
    element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED
  )
}

export function isFixedRootMultiPageContainer(element) {
  return (
    isRootMultiPageContainer(element) &&
    element.behaviour === PAGE_ELEMENT_BEHAVIOURS.FIXED
  )
}

export function getMultiPageElementPositioningGroups(elements) {
  return elements.reduce((groups, element) => {
    const isFixed = isFixedRootMultiPageContainer(element)
    const lastGroup = groups[groups.length - 1]

    if (!lastGroup || lastGroup.isFixed !== isFixed) {
      groups.push({
        key: `${isFixed ? 'fixed' : 'normal'}-${element.id}`,
        isFixed,
        elements: [element],
      })
    } else {
      lastGroup.elements.push(element)
    }

    return groups
  }, [])
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
