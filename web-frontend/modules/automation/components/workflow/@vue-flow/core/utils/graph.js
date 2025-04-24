import { markRaw } from 'vue'
import { isDef, snapPosition, warn } from '.'

export function nodeToRect(node) {
  return {
    ...(node.computedPosition || { x: 0, y: 0 }),
    width: node.dimensions.width || 0,
    height: node.dimensions.height || 0,
  }
}

export function getOverlappingArea(rectA, rectB) {
  const xOverlap = Math.max(
    0,
    Math.min(rectA.x + rectA.width, rectB.x + rectB.width) -
      Math.max(rectA.x, rectB.x)
  )
  const yOverlap = Math.max(
    0,
    Math.min(rectA.y + rectA.height, rectB.y + rectB.height) -
      Math.max(rectA.y, rectB.y)
  )

  return Math.ceil(xOverlap * yOverlap)
}

export function getDimensions(node) {
  return {
    width: node.offsetWidth,
    height: node.offsetHeight,
  }
}

export function clamp(val, min = 0, max = 1) {
  return Math.min(Math.max(val, min), max)
}

export function clampPosition(position, extent) {
  return {
    x: clamp(position.x, extent[0][0], extent[1][0]),
    y: clamp(position.y, extent[0][1], extent[1][1]),
  }
}

export function getHostForElement(element) {
  const doc = element.getRootNode()

  if ('elementFromPoint' in doc) {
    return doc
  }

  return window.document
}

export function isEdge(element) {
  return (
    element &&
    typeof element === 'object' &&
    'id' in element &&
    'source' in element &&
    'target' in element
  )
}

export function isGraphEdge(element) {
  return isEdge(element) && 'sourceNode' in element && 'targetNode' in element
}

export function isNode(element) {
  return (
    element &&
    typeof element === 'object' &&
    'id' in element &&
    'position' in element &&
    !isEdge(element)
  )
}

export function isGraphNode(element) {
  return isNode(element) && 'computedPosition' in element
}

function isNumeric(n) {
  return !Number.isNaN(n) && Number.isFinite(n)
}

export function isRect(obj) {
  return (
    isNumeric(obj.width) &&
    isNumeric(obj.height) &&
    isNumeric(obj.x) &&
    isNumeric(obj.y)
  )
}

export function parseNode(node, existingNode, parentNode) {
  const initialState = {
    id: node.id.toString(),
    type: node.type ?? 'default',
    dimensions: markRaw({
      width: 0,
      height: 0,
    }),
    computedPosition: markRaw({
      z: 0,
      ...node.position,
    }),
    // todo: shouldn't be defined initially, as we want to use handleBounds to check if a node was actually initialized or not
    handleBounds: {
      source: [],
      target: [],
    },
    draggable: undefined,
    selectable: undefined,
    connectable: undefined,
    focusable: undefined,
    selected: false,
    dragging: false,
    resizing: false,
    initialized: false,
    isParent: false,
    position: {
      x: 0,
      y: 0,
    },
    data: isDef(node.data) ? node.data : {},
    events: markRaw(isDef(node.events) ? node.events : {}),
  }

  return Object.assign(existingNode ?? initialState, node, {
    id: node.id.toString(),
    parentNode,
  })
}

export function parseEdge(edge, existingEdge, defaultEdgeOptions) {
  const initialState = {
    id: edge.id.toString(),
    type: edge.type ?? existingEdge?.type ?? 'default',
    source: edge.source.toString(),
    target: edge.target.toString(),
    sourceHandle: edge.sourceHandle?.toString(),
    targetHandle: edge.targetHandle?.toString(),
    updatable: edge.updatable ?? defaultEdgeOptions?.updatable,
    selectable: edge.selectable ?? defaultEdgeOptions?.selectable,
    focusable: edge.focusable ?? defaultEdgeOptions?.focusable,
    data: isDef(edge.data) ? edge.data : {},
    events: markRaw(isDef(edge.events) ? edge.events : {}),
    label: edge.label ?? '',
    interactionWidth:
      edge.interactionWidth ?? defaultEdgeOptions?.interactionWidth,
    ...(defaultEdgeOptions ?? {}),
  }

  return Object.assign(existingEdge ?? initialState, edge, {
    id: edge.id.toString(),
  })
}

function getConnectedElements(nodeOrId, nodes, edges, dir) {
  const id = typeof nodeOrId === 'string' ? nodeOrId : nodeOrId.id

  const connectedIds = new Set()

  const origin = dir === 'source' ? 'target' : 'source'

  for (const edge of edges) {
    if (edge[origin] === id) {
      connectedIds.add(edge[dir])
    }
  }

  return nodes.filter((n) => connectedIds.has(n.id))
}

export function getOutgoers(...args) {
  if (args.length === 3) {
    const [nodeOrId, nodes, edges] = args
    return getConnectedElements(nodeOrId, nodes, edges, 'target')
  }

  const [nodeOrId, elements] = args
  const nodeId = typeof nodeOrId === 'string' ? nodeOrId : nodeOrId.id

  const outgoers = elements.filter((el) => isEdge(el) && el.source === nodeId)

  return outgoers.map((edge) =>
    elements.find((el) => isNode(el) && el.id === edge.target)
  )
}

export function getIncomers(...args) {
  if (args.length === 3) {
    const [nodeOrId, nodes, edges] = args
    return getConnectedElements(nodeOrId, nodes, edges, 'source')
  }

  const [nodeOrId, elements] = args
  const nodeId = typeof nodeOrId === 'string' ? nodeOrId : nodeOrId.id

  const incomers = elements.filter((el) => isEdge(el) && el.target === nodeId)

  return incomers.map((edge) =>
    elements.find((el) => isNode(el) && el.id === edge.source)
  )
}

export function getEdgeId({ source, sourceHandle, target, targetHandle }) {
  return `vueflow__edge-${source}${sourceHandle ?? ''}-${target}${
    targetHandle ?? ''
  }`
}

export function connectionExists(edge, elements) {
  return elements.some(
    (el) =>
      isEdge(el) &&
      el.source === edge.source &&
      el.target === edge.target &&
      (el.sourceHandle === edge.sourceHandle ||
        (!el.sourceHandle && !edge.sourceHandle)) &&
      (el.targetHandle === edge.targetHandle ||
        (!el.targetHandle && !edge.targetHandle))
  )
}

/**
 * @deprecated Use store instance and call `addEdges` with template-ref or the one received by `onPaneReady` instead
 *
 * Intended for options API
 * In composition API you can access utilities from `useVueFlow`
 */
export function addEdge(edgeParams, elements, defaults) {
  if (!edgeParams.source || !edgeParams.target) {
    warn("Can't create edge. An edge needs a source and a target.")
    return elements
  }

  let edge

  if (isEdge(edgeParams)) {
    edge = { ...edgeParams }
  } else {
    edge = {
      ...edgeParams,
      id: getEdgeId(edgeParams),
    }
  }

  edge = parseEdge(edge, undefined, defaults)

  if (connectionExists(edge, elements)) {
    return elements
  }

  elements.push(edge)

  return elements
}

/**
 * @deprecated Use store instance and call `updateEdge` with template-ref or the one received by `onPaneReady` instead
 *
 * Intended for options API
 * In composition API you can access utilities from `useVueFlow`
 */
export function updateEdge(oldEdge, newConnection, elements) {
  if (!newConnection.source || !newConnection.target) {
    warn("Can't create new edge. An edge needs a source and a target.")
    return elements
  }

  const foundEdge = elements.find((e) => isEdge(e) && e.id === oldEdge.id)

  if (!foundEdge) {
    warn(`The old edge with id=${oldEdge.id} does not exist.`)
    return elements
  }

  // Remove old edge and create the new edge with parameters of old edge.
  const edge = {
    ...oldEdge,
    id: getEdgeId(newConnection),
    source: newConnection.source,
    target: newConnection.target,
    sourceHandle: newConnection.sourceHandle,
    targetHandle: newConnection.targetHandle,
  }
  elements.splice(elements.indexOf(foundEdge), 1, edge)

  return elements.filter((e) => e.id !== oldEdge.id)
}

export function rendererPointToPoint({ x, y }, { x: tx, y: ty, zoom: tScale }) {
  return {
    x: x * tScale + tx,
    y: y * tScale + ty,
  }
}

export function pointToRendererPoint(
  { x, y },
  { x: tx, y: ty, zoom: tScale },
  snapToGrid = false,
  snapGrid = [1, 1]
) {
  const position = {
    x: (x - tx) / tScale,
    y: (y - ty) / tScale,
  }

  return snapToGrid ? snapPosition(position, snapGrid) : position
}

function getBoundsOfBoxes(box1, box2) {
  return {
    x: Math.min(box1.x, box2.x),
    y: Math.min(box1.y, box2.y),
    x2: Math.max(box1.x2, box2.x2),
    y2: Math.max(box1.y2, box2.y2),
  }
}

export function rectToBox({ x, y, width, height }) {
  return {
    x,
    y,
    x2: x + width,
    y2: y + height,
  }
}

export function boxToRect({ x, y, x2, y2 }) {
  return {
    x,
    y,
    width: x2 - x,
    height: y2 - y,
  }
}

// todo: fix typo
export function getBoundsofRects(rect1, rect2) {
  return boxToRect(getBoundsOfBoxes(rectToBox(rect1), rectToBox(rect2)))
}

export function getRectOfNodes(nodes) {
  let box = {
    x: Number.POSITIVE_INFINITY,
    y: Number.POSITIVE_INFINITY,
    x2: Number.NEGATIVE_INFINITY,
    y2: Number.NEGATIVE_INFINITY,
  }

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i]
    box = getBoundsOfBoxes(
      box,
      rectToBox({
        ...node.computedPosition,
        ...node.dimensions,
      })
    )
  }

  return boxToRect(box)
}

export function getNodesInside(
  nodes,
  rect,
  viewport = { x: 0, y: 0, zoom: 1 },
  partially = false,
  // set excludeNonSelectableNodes if you want to pay attention to the nodes "selectable" attribute
  excludeNonSelectableNodes = false
) {
  const paneRect = {
    ...pointToRendererPoint(rect, viewport),
    width: rect.width / viewport.zoom,
    height: rect.height / viewport.zoom,
  }

  const visibleNodes = []

  for (const node of nodes) {
    const { dimensions, selectable = true, hidden = false } = node
    const width = dimensions.width ?? node.width ?? null
    const height = dimensions.height ?? node.height ?? null

    if ((excludeNonSelectableNodes && !selectable) || hidden) {
      continue
    }

    const overlappingArea = getOverlappingArea(paneRect, nodeToRect(node))
    const notInitialized = width === null || height === null

    const partiallyVisible = partially && overlappingArea > 0
    const area = (width ?? 0) * (height ?? 0)
    const isVisible =
      notInitialized || partiallyVisible || overlappingArea >= area

    if (isVisible || node.dragging) {
      visibleNodes.push(node)
    }
  }

  return visibleNodes
}

export function getConnectedEdges(nodesOrId, edges) {
  const nodeIds = new Set()

  if (typeof nodesOrId === 'string') {
    nodeIds.add(nodesOrId)
  } else if (nodesOrId.length >= 1) {
    for (const n of nodesOrId) {
      nodeIds.add(n.id)
    }
  }

  return edges.filter(
    (edge) => nodeIds.has(edge.source) || nodeIds.has(edge.target)
  )
}

export function getConnectedNodes(nodes, edges) {
  const nodeIds = new Set()

  for (const node of nodes) {
    nodeIds.add(typeof node === 'string' ? node : node.id)
  }

  const connectedNodeIds = edges.reduce((acc, edge) => {
    if (nodeIds.has(edge.source)) {
      acc.add(edge.target)
    }

    if (nodeIds.has(edge.target)) {
      acc.add(edge.source)
    }

    return acc
  }, new Set())

  return nodes.filter((node) =>
    connectedNodeIds.has(typeof node === 'string' ? node : node.id)
  )
}

export function getTransformForBounds(
  bounds,
  width,
  height,
  minZoom,
  maxZoom,
  padding = 0.1,
  offset = { x: 0, y: 0 }
) {
  const xZoom = width / (bounds.width * (1 + padding))
  const yZoom = height / (bounds.height * (1 + padding))
  const zoom = Math.min(xZoom, yZoom)
  const clampedZoom = clamp(zoom, minZoom, maxZoom)
  const boundsCenterX = bounds.x + bounds.width / 2
  const boundsCenterY = bounds.y + bounds.height / 2
  const x = width / 2 - boundsCenterX * clampedZoom + (offset.x ?? 0)
  const y = height / 2 - boundsCenterY * clampedZoom + (offset.y ?? 0)

  return { x, y, zoom: clampedZoom }
}

export function getXYZPos(parentPos, computedPosition) {
  return {
    x: computedPosition.x + parentPos.x,
    y: computedPosition.y + parentPos.y,
    z:
      (parentPos.z > computedPosition.z ? parentPos.z : computedPosition.z) + 1,
  }
}

export function isParentSelected(node, findNode) {
  if (!node.parentNode) {
    return false
  }

  const parent = findNode(node.parentNode)
  if (!parent) {
    return false
  }

  if (parent.selected) {
    return true
  }

  return isParentSelected(parent, findNode)
}

export function getMarkerId(marker, vueFlowId) {
  if (typeof marker === 'undefined') {
    return ''
  }

  if (typeof marker === 'string') {
    return marker
  }

  const idPrefix = vueFlowId ? `${vueFlowId}__` : ''

  return `${idPrefix}${Object.keys(marker)
    .sort()
    .map((key) => `${key}=${marker[key]}`)
    .join('&')}`
}
