import { getBezierEdgeCenter } from './general'

// Définition locale de Position au lieu de l'importer
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

function calculateControlOffset(distance, curvature) {
  if (distance >= 0) {
    return 0.5 * distance
  } else {
    return curvature * 25 * Math.sqrt(-distance)
  }
}

function getControlWithCurvature({ pos, x1, y1, x2, y2, c }) {
  let ctX, ctY
  switch (pos) {
    case Position.Left:
      ctX = x1 - calculateControlOffset(x1 - x2, c)
      ctY = y1
      break
    case Position.Right:
      ctX = x1 + calculateControlOffset(x2 - x1, c)
      ctY = y1
      break
    case Position.Top:
      ctX = x1
      ctY = y1 - calculateControlOffset(y1 - y2, c)
      break
    case Position.Bottom:
      ctX = x1
      ctY = y1 + calculateControlOffset(y2 - y1, c)
      break
  }
  return [ctX, ctY]
}

/**
 * Get a bezier path from source to target handle
 * @public
 *
 * @param {Object} bezierPathParams
 * @param {number} bezierPathParams.sourceX - The x position of the source handle
 * @param {number} bezierPathParams.sourceY - The y position of the source handle
 * @param {string} [bezierPathParams.sourcePosition=Position.Bottom] - The position of the source handle
 * @param {number} bezierPathParams.targetX - The x position of the target handle
 * @param {number} bezierPathParams.targetY - The y position of the target handle
 * @param {string} [bezierPathParams.targetPosition=Position.Top] - The position of the target handle
 * @param {number} [bezierPathParams.curvature=0.25] - The curvature of the edge
 * @returns {Array} A path string you can use in an SVG, the labelX and labelY position (center of path) and offsetX, offsetY between source handle and label
 */
export function getBezierPath(bezierPathParams) {
  const {
    sourceX,
    sourceY,
    sourcePosition = Position.Bottom,
    targetX,
    targetY,
    targetPosition = Position.Top,
    curvature = 0.25,
  } = bezierPathParams

  const [sourceControlX, sourceControlY] = getControlWithCurvature({
    pos: sourcePosition,
    x1: sourceX,
    y1: sourceY,
    x2: targetX,
    y2: targetY,
    c: curvature,
  })
  const [targetControlX, targetControlY] = getControlWithCurvature({
    pos: targetPosition,
    x1: targetX,
    y1: targetY,
    x2: sourceX,
    y2: sourceY,
    c: curvature,
  })
  const [labelX, labelY, offsetX, offsetY] = getBezierEdgeCenter({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourceControlX,
    sourceControlY,
    targetControlX,
    targetControlY,
  })

  return [
    `M${sourceX},${sourceY} C${sourceControlX},${sourceControlY} ${targetControlX},${targetControlY} ${targetX},${targetY}`,
    labelX,
    labelY,
    offsetX,
    offsetY,
  ]
}
