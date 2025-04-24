import { nextTick } from 'vue'
import { getDimensions } from '.'

export function getHandleBounds(type, nodeElement, nodeBounds, zoom) {
  const handles = nodeElement.querySelectorAll(`.vue-flow__handle.${type}`)

  const handlesArray = Array.from(handles)

  return handlesArray.map((handle) => {
    const handleBounds = handle.getBoundingClientRect()

    return {
      id: handle.getAttribute('data-handleid'),
      position: handle.getAttribute('data-handlepos'),
      nodeId: handle.getAttribute('data-nodeid'),
      type,
      x: (handleBounds.left - nodeBounds.left) / zoom,
      y: (handleBounds.top - nodeBounds.top) / zoom,
      ...getDimensions(handle),
    }
  })
}

export function handleNodeClick(
  node,
  multiSelectionActive,
  addSelectedNodes,
  removeSelectedNodes,
  nodesSelectionActive,
  unselect = false,
  nodeEl
) {
  nodesSelectionActive.value = false

  if (!node.selected) {
    addSelectedNodes([node])
  } else if (unselect || (node.selected && multiSelectionActive)) {
    removeSelectedNodes([node])

    nextTick(() => {
      nodeEl.blur()
    })
  }
}
