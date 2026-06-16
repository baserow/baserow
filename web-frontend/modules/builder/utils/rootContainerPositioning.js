import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

// Only root-level simple containers can opt into page-level fixed or sticky positioning.
export function isPositionedRootContainer(element) {
  return (
    element.type === 'simple_container' &&
    !element.parent_element_id &&
    [PAGE_ELEMENT_BEHAVIOURS.STICKY, PAGE_ELEMENT_BEHAVIOURS.FIXED].includes(
      element.behaviour
    ) &&
    [PAGE_ELEMENT_ALIGNMENTS.TOP, PAGE_ELEMENT_ALIGNMENTS.BOTTOM].includes(
      element.alignment || PAGE_ELEMENT_ALIGNMENTS.TOP
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
  const alignment = element.alignment || PAGE_ELEMENT_ALIGNMENTS.TOP

  return {
    'element--positioned': true,
    [`element--position-${behaviour}`]: true,
    [`element--position-alignment-${alignment}`]: true,
  }
}
