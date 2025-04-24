export function isMouseEvent(event) {
  return 'clientX' in event
}

export function isUseDragEvent(event) {
  return 'sourceEvent' in event
}

export function getEventPosition(event, bounds) {
  const isMouse = isMouseEvent(event)

  const evtX = isMouse ? event.clientX : event.touches?.[0].clientX
  const evtY = isMouse ? event.clientY : event.touches?.[0].clientY

  return {
    x: evtX - (bounds?.left ?? 0),
    y: evtY - (bounds?.top ?? 0),
  }
}

export const isMacOs = () =>
  typeof navigator !== 'undefined' && navigator?.userAgent?.indexOf('Mac') >= 0

export function getNodeDimensions(node) {
  return {
    width: node.dimensions?.width ?? node.width ?? 0,
    height: node.dimensions?.height ?? node.height ?? 0,
  }
}

export function snapPosition(position, snapGrid = [1, 1]) {
  return {
    x: snapGrid[0] * Math.round(position.x / snapGrid[0]),
    y: snapGrid[1] * Math.round(position.y / snapGrid[1]),
  }
}
