import { h } from 'vue'

// Définition locale de Position au lieu de l'importer
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

/**
 * Shift X coordinate based on position
 * @param {number} x - X coordinate
 * @param {number} shift - Amount to shift
 * @param {string} position - Position enum value
 * @returns {number} Shifted X coordinate
 */
function shiftX(x, shift, position) {
  if (position === Position.Left) {
    return x - shift
  }
  if (position === Position.Right) {
    return x + shift
  }
  return x
}

/**
 * Shift Y coordinate based on position
 * @param {number} y - Y coordinate
 * @param {number} shift - Amount to shift
 * @param {string} position - Position enum value
 * @returns {number} Shifted Y coordinate
 */
function shiftY(y, shift, position) {
  if (position === Position.Top) {
    return y - shift
  }
  if (position === Position.Bottom) {
    return y + shift
  }
  return y
}

/**
 * Edge Anchor component
 * @param {Object} props - Component props
 * @param {number} [props.radius=10] - Circle radius
 * @param {number} [props.centerX=0] - Center X coordinate
 * @param {number} [props.centerY=0] - Center Y coordinate
 * @param {string} [props.position=Position.Top] - Anchor position
 * @param {string} props.type - Anchor type
 * @returns {VNode} Virtual node
 */
const EdgeAnchor = function ({
  radius = 10,
  centerX = 0,
  centerY = 0,
  position = Position.Top,
  type,
}) {
  return h('circle', {
    class: `vue-flow__edgeupdater vue-flow__edgeupdater-${type}`,
    cx: shiftX(centerX, radius, position),
    cy: shiftY(centerY, radius, position),
    r: radius,
    stroke: 'transparent',
    fill: 'transparent',
  })
}

EdgeAnchor.props = ['radius', 'centerX', 'centerY', 'position', 'type']
EdgeAnchor.compatConfig = { MODE: 3 }

export default EdgeAnchor
