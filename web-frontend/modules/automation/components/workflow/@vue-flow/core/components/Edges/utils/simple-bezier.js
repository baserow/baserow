import { getBezierEdgeCenter } from './general'

// Définition locale de Position au lieu de l'importer
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

/**
 * Get control point for a simple bezier curve
 * @param {Object} params
 * @param {string} params.pos - Position (top, right, bottom, left)
 * @param {number} params.x1 - Source X coordinate
 * @param {number} params.y1 - Source Y coordinate
 * @param {number} params.x2 - Target X coordinate
 * @param {number} params.y2 - Target Y coordinate
 * @returns {Array} [controlX, controlY]
 */
function getControl({ pos, x1, y1, x2, y2 }) {
  let ctX, ctY
  switch (pos) {
    case Position.Left:
    case Position.Right:
      ctX = 0.5 * (x1 + x2)
      ctY = y1
      break
    case Position.Top:
    case Position.Bottom:
      ctX = x1
      ctY = 0.5 * (y1 + y2)
      break
  }
  return [ctX, ctY]
}

/**
 * Get a simple bezier path from source to target handle (no curvature)
 * @public
 *
 * @param {Object} simpleBezierPathParams
 * @param {number} simpleBezierPathParams.sourceX - The x position of the source handle
 * @param {number} simpleBezierPathParams.sourceY - The y position of the source handle
 * @param {string} [simpleBezierPathParams.sourcePosition=Position.Bottom] - The position of the source handle
 * @param {number} simpleBezierPathParams.targetX - The x position of the target handle
 * @param {number} simpleBezierPathParams.targetY - The y position of the target handle
 * @param {string} [simpleBezierPathParams.targetPosition=Position.Top] - The position of the target handle
 * @returns {Array} A path string you can use in an SVG, the labelX and labelY position (center of path) and offsetX, offsetY between source handle and label
 */
export function getSimpleBezierPath(simpleBezierPathParams) {
  const {
    sourceX,
    sourceY,
    sourcePosition = Position.Bottom,
    targetX,
    targetY,
    targetPosition = Position.Top,
  } = simpleBezierPathParams

  const [sourceControlX, sourceControlY] = getControl({
    pos: sourcePosition,
    x1: sourceX,
    y1: sourceY,
    x2: targetX,
    y2: targetY,
  })
  const [targetControlX, targetControlY] = getControl({
    pos: targetPosition,
    x1: targetX,
    y1: targetY,
    x2: sourceX,
    y2: sourceY,
  })

  const [centerX, centerY, offsetX, offsetY] = getBezierEdgeCenter({
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
    centerX,
    centerY,
    offsetX,
    offsetY,
  ]
}
