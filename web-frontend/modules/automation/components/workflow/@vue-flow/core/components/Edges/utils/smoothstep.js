import { getSimpleEdgeCenter } from './general'

// Définition locale de Position au lieu de l'importer
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

const handleDirections = {
  [Position.Left]: { x: -1, y: 0 },
  [Position.Right]: { x: 1, y: 0 },
  [Position.Top]: { x: 0, y: -1 },
  [Position.Bottom]: { x: 0, y: 1 },
}

/**
 * Get direction based on source and target positions
 * @param {Object} params
 * @param {Object} params.source - Source position with x,y coordinates
 * @param {string} params.sourcePosition - Position of source handle
 * @param {Object} params.target - Target position with x,y coordinates
 * @returns {Object} Direction object with x,y values
 */
function getDirection({ source, sourcePosition = Position.Bottom, target }) {
  if (sourcePosition === Position.Left || sourcePosition === Position.Right) {
    return source.x < target.x ? { x: 1, y: 0 } : { x: -1, y: 0 }
  }
  return source.y < target.y ? { x: 0, y: 1 } : { x: 0, y: -1 }
}

/**
 * Calculate distance between two points
 * @param {Object} a - First point with x,y coordinates
 * @param {Object} b - Second point with x,y coordinates
 * @returns {number} Distance between points
 */
function distance(a, b) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
}

/**
 * Calculate points for edge routing
 * @param {Object} params
 * @param {Object} params.source - Source position with x,y coordinates
 * @param {string} params.sourcePosition - Position of source handle
 * @param {Object} params.target - Target position with x,y coordinates
 * @param {string} params.targetPosition - Position of target handle
 * @param {Object} params.center - Center position
 * @param {number} params.offset - Offset value
 * @returns {Array} Array containing points, centerX, centerY, offsetX, offsetY
 */
function getPoints({
  source,
  sourcePosition = Position.Bottom,
  target,
  targetPosition = Position.Top,
  center,
  offset,
}) {
  const sourceDir = handleDirections[sourcePosition]
  const targetDir = handleDirections[targetPosition]
  const sourceGapped = {
    x: source.x + sourceDir.x * offset,
    y: source.y + sourceDir.y * offset,
  }
  const targetGapped = {
    x: target.x + targetDir.x * offset,
    y: target.y + targetDir.y * offset,
  }
  const dir = getDirection({
    source: sourceGapped,
    sourcePosition,
    target: targetGapped,
  })
  const dirAccessor = dir.x !== 0 ? 'x' : 'y'
  const currDir = dir[dirAccessor]

  let points
  let centerX, centerY

  const sourceGapOffset = { x: 0, y: 0 }
  const targetGapOffset = { x: 0, y: 0 }

  const [defaultCenterX, defaultCenterY, defaultOffsetX, defaultOffsetY] =
    getSimpleEdgeCenter({
      sourceX: source.x,
      sourceY: source.y,
      targetX: target.x,
      targetY: target.y,
    })

  // opposite handle positions, default case
  if (sourceDir[dirAccessor] * targetDir[dirAccessor] === -1) {
    centerX = center.x ?? defaultCenterX
    centerY = center.y ?? defaultCenterY
    //    --->
    //    |
    // >---
    const verticalSplit = [
      { x: centerX, y: sourceGapped.y },
      { x: centerX, y: targetGapped.y },
    ]
    //    |
    //  ---
    //  |
    const horizontalSplit = [
      { x: sourceGapped.x, y: centerY },
      { x: targetGapped.x, y: centerY },
    ]

    if (sourceDir[dirAccessor] === currDir) {
      points = dirAccessor === 'x' ? verticalSplit : horizontalSplit
    } else {
      points = dirAccessor === 'x' ? horizontalSplit : verticalSplit
    }
  } else {
    // sourceTarget means we take x from source and y from target, targetSource is the opposite
    const sourceTarget = [{ x: sourceGapped.x, y: targetGapped.y }]
    const targetSource = [{ x: targetGapped.x, y: sourceGapped.y }]
    // this handles edges with same handle positions
    if (dirAccessor === 'x') {
      points = sourceDir.x === currDir ? targetSource : sourceTarget
    } else {
      points = sourceDir.y === currDir ? sourceTarget : targetSource
    }

    if (sourcePosition === targetPosition) {
      const diff = Math.abs(source[dirAccessor] - target[dirAccessor])

      // if an edge goes from right to right for example (sourcePosition === targetPosition) and the distance between source.x and target.x is less than the offset, the added point and the gapped source/target will overlap. This leads to a weird edge path. To avoid this we add a gapOffset to the source/target
      if (diff <= offset) {
        const gapOffset = Math.min(offset - 1, offset - diff)
        if (sourceDir[dirAccessor] === currDir) {
          sourceGapOffset[dirAccessor] =
            (sourceGapped[dirAccessor] > source[dirAccessor] ? -1 : 1) *
            gapOffset
        } else {
          targetGapOffset[dirAccessor] =
            (targetGapped[dirAccessor] > target[dirAccessor] ? -1 : 1) *
            gapOffset
        }
      }
    }

    // these are conditions for handling mixed handle positions like Right -> Bottom for example
    if (sourcePosition !== targetPosition) {
      const dirAccessorOpposite = dirAccessor === 'x' ? 'y' : 'x'
      const isSameDir =
        sourceDir[dirAccessor] === targetDir[dirAccessorOpposite]
      const sourceGtTargetOppo =
        sourceGapped[dirAccessorOpposite] > targetGapped[dirAccessorOpposite]
      const sourceLtTargetOppo =
        sourceGapped[dirAccessorOpposite] < targetGapped[dirAccessorOpposite]
      const flipSourceTarget =
        (sourceDir[dirAccessor] === 1 &&
          ((!isSameDir && sourceGtTargetOppo) ||
            (isSameDir && sourceLtTargetOppo))) ||
        (sourceDir[dirAccessor] !== 1 &&
          ((!isSameDir && sourceLtTargetOppo) ||
            (isSameDir && sourceGtTargetOppo)))

      if (flipSourceTarget) {
        points = dirAccessor === 'x' ? sourceTarget : targetSource
      }
    }

    const sourceGapPoint = {
      x: sourceGapped.x + sourceGapOffset.x,
      y: sourceGapped.y + sourceGapOffset.y,
    }
    const targetGapPoint = {
      x: targetGapped.x + targetGapOffset.x,
      y: targetGapped.y + targetGapOffset.y,
    }
    const maxXDistance = Math.max(
      Math.abs(sourceGapPoint.x - points[0].x),
      Math.abs(targetGapPoint.x - points[0].x)
    )
    const maxYDistance = Math.max(
      Math.abs(sourceGapPoint.y - points[0].y),
      Math.abs(targetGapPoint.y - points[0].y)
    )

    // we want to place the label on the longest segment of the edge
    if (maxXDistance >= maxYDistance) {
      centerX = (sourceGapPoint.x + targetGapPoint.x) / 2
      centerY = points[0].y
    } else {
      centerX = points[0].x
      centerY = (sourceGapPoint.y + targetGapPoint.y) / 2
    }
  }

  const pathPoints = [
    source,
    {
      x: sourceGapped.x + sourceGapOffset.x,
      y: sourceGapped.y + sourceGapOffset.y,
    },
    ...points,
    {
      x: targetGapped.x + targetGapOffset.x,
      y: targetGapped.y + targetGapOffset.y,
    },
    target,
  ]

  return [pathPoints, centerX, centerY, defaultOffsetX, defaultOffsetY]
}

/**
 * Get a bend for smooth step path
 * @param {Object} a - First point with x,y coordinates
 * @param {Object} b - Second point with x,y coordinates
 * @param {Object} c - Third point with x,y coordinates
 * @param {number} size - Bend size
 * @returns {string} Path segment string
 */
function getBend(a, b, c, size) {
  const bendSize = Math.min(distance(a, b) / 2, distance(b, c) / 2, size)
  const { x, y } = b

  // no bend
  if ((a.x === x && x === c.x) || (a.y === y && y === c.y)) {
    return `L${x} ${y}`
  }

  // first segment is horizontal
  if (a.y === y) {
    const xDir = a.x < c.x ? -1 : 1
    const yDir = a.y < c.y ? 1 : -1
    return `L ${x + bendSize * xDir},${y}Q ${x},${y} ${x},${
      y + bendSize * yDir
    }`
  }

  const xDir = a.x < c.x ? 1 : -1
  const yDir = a.y < c.y ? -1 : 1
  return `L ${x},${y + bendSize * yDir}Q ${x},${y} ${x + bendSize * xDir},${y}`
}

/**
 * Get a smooth step path from source to target handle
 * @public
 *
 * @param {Object} smoothStepPathParams
 * @param {number} smoothStepPathParams.sourceX - The x position of the source handle
 * @param {number} smoothStepPathParams.sourceY - The y position of the source handle
 * @param {string} [smoothStepPathParams.sourcePosition=Position.Bottom] - The position of the source handle
 * @param {number} smoothStepPathParams.targetX - The x position of the target handle
 * @param {number} smoothStepPathParams.targetY - The y position of the target handle
 * @param {string} [smoothStepPathParams.targetPosition=Position.Top] - The position of the target handle
 * @param {number} [smoothStepPathParams.borderRadius=5] - The border radius of the edge
 * @param {number} [smoothStepPathParams.centerX] - The x position of the center point
 * @param {number} [smoothStepPathParams.centerY] - The y position of the center point
 * @param {number} [smoothStepPathParams.offset=20] - Offset value
 * @returns {Array} A path string you can use in an SVG, the labelX and labelY position (center of path) and offsetX, offsetY between source handle and label
 */
export function getSmoothStepPath(smoothStepPathParams) {
  const {
    sourceX,
    sourceY,
    sourcePosition = Position.Bottom,
    targetX,
    targetY,
    targetPosition = Position.Top,
    borderRadius = 5,
    centerX,
    centerY,
    offset = 20,
  } = smoothStepPathParams

  const [points, labelX, labelY, offsetX, offsetY] = getPoints({
    source: { x: sourceX, y: sourceY },
    sourcePosition,
    target: { x: targetX, y: targetY },
    targetPosition,
    center: { x: centerX, y: centerY },
    offset,
  })

  const path = points.reduce((res, p, i) => {
    let segment

    if (i > 0 && i < points.length - 1) {
      segment = getBend(points[i - 1], p, points[i + 1], borderRadius)
    } else {
      segment = `${i === 0 ? 'M' : 'L'}${p.x} ${p.y}`
    }

    res += segment

    return res
  }, '')

  return [path, labelX, labelY, offsetX, offsetY]
}
