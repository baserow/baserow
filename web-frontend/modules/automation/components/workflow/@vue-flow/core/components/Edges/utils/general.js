/**
 * @typedef {Array} EdgePathParams
 * @property {string} 0 - SVG path string
 * @property {number} 1 - Label X position
 * @property {number} 2 - Label Y position
 * @property {number} 3 - Offset X
 * @property {number} 4 - Offset Y
 */

/**
 * Get the center position for straight edges and simple smoothstep edges
 * @param {Object} params
 * @param {number} params.sourceX - Source X coordinate
 * @param {number} params.sourceY - Source Y coordinate
 * @param {number} params.targetX - Target X coordinate
 * @param {number} params.targetY - Target Y coordinate
 * @returns {Array} [centerX, centerY, xOffset, yOffset]
 */
export function getSimpleEdgeCenter({ sourceX, sourceY, targetX, targetY }) {
  const xOffset = Math.abs(targetX - sourceX) / 2
  const centerX = targetX < sourceX ? targetX + xOffset : targetX - xOffset

  const yOffset = Math.abs(targetY - sourceY) / 2
  const centerY = targetY < sourceY ? targetY + yOffset : targetY - yOffset

  return [centerX, centerY, xOffset, yOffset]
}

/**
 * Get the center position for bezier edges
 * @param {Object} params
 * @param {number} params.sourceX - Source X coordinate
 * @param {number} params.sourceY - Source Y coordinate
 * @param {number} params.targetX - Target X coordinate
 * @param {number} params.targetY - Target Y coordinate
 * @param {number} params.sourceControlX - Source control point X coordinate
 * @param {number} params.sourceControlY - Source control point Y coordinate
 * @param {number} params.targetControlX - Target control point X coordinate
 * @param {number} params.targetControlY - Target control point Y coordinate
 * @returns {Array} [centerX, centerY, offsetX, offsetY]
 */
export function getBezierEdgeCenter({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourceControlX,
  sourceControlY,
  targetControlX,
  targetControlY,
}) {
  // cubic bezier t=0.5 mid point, not the actual mid point, but easy to calculate
  // https://stackoverflow.com/questions/67516101/how-to-find-distance-mid-point-of-bezier-curve
  const centerX =
    sourceX * 0.125 +
    sourceControlX * 0.375 +
    targetControlX * 0.375 +
    targetX * 0.125
  const centerY =
    sourceY * 0.125 +
    sourceControlY * 0.375 +
    targetControlY * 0.375 +
    targetY * 0.125
  const offsetX = Math.abs(centerX - sourceX)
  const offsetY = Math.abs(centerY - sourceY)

  return [centerX, centerY, offsetX, offsetY]
}
