import { getSimpleEdgeCenter } from './general'

/**
 * Get a straight path from source to target handle
 * @public
 *
 * @param {Object} straightEdgeParams
 * @param {number} straightEdgeParams.sourceX - The x position of the source handle
 * @param {number} straightEdgeParams.sourceY - The y position of the source handle
 * @param {number} straightEdgeParams.targetX - The x position of the target handle
 * @param {number} straightEdgeParams.targetY - The y position of the target handle
 * @returns {Array} A path string you can use in an SVG, the labelX and labelY position (center of path) and offsetX, offsetY between source handle and label
 */
export function getStraightPath(straightEdgeParams) {
  const { sourceX, sourceY, targetX, targetY } = straightEdgeParams

  const [centerX, centerY, offsetX, offsetY] = getSimpleEdgeCenter({
    sourceX,
    sourceY,
    targetX,
    targetY,
  })

  return [
    `M ${sourceX},${sourceY}L ${targetX},${targetY}`,
    centerX,
    centerY,
    offsetX,
    offsetY,
  ]
}
