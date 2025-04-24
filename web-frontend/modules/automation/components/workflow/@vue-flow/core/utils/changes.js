import { nextTick } from 'vue'
import { isGraphNode } from '.'

function handleParentExpand(updateItem, parent) {
  if (parent) {
    const extendWidth =
      updateItem.position.x +
      updateItem.dimensions.width -
      parent.dimensions.width
    const extendHeight =
      updateItem.position.y +
      updateItem.dimensions.height -
      parent.dimensions.height

    if (
      extendWidth > 0 ||
      extendHeight > 0 ||
      updateItem.position.x < 0 ||
      updateItem.position.y < 0
    ) {
      let parentStyles = {}

      if (typeof parent.style === 'function') {
        parentStyles = { ...parent.style(parent) }
      } else if (parent.style) {
        parentStyles = { ...parent.style }
      }

      parentStyles.width = parentStyles.width ?? `${parent.dimensions.width}px`
      parentStyles.height =
        parentStyles.height ?? `${parent.dimensions.height}px`

      if (extendWidth > 0) {
        if (typeof parentStyles.width === 'string') {
          const currWidth = Number(parentStyles.width.replace('px', ''))
          parentStyles.width = `${currWidth + extendWidth}px`
        } else {
          parentStyles.width += extendWidth
        }
      }

      if (extendHeight > 0) {
        if (typeof parentStyles.height === 'string') {
          const currWidth = Number(parentStyles.height.replace('px', ''))
          parentStyles.height = `${currWidth + extendHeight}px`
        } else {
          parentStyles.height += extendHeight
        }
      }

      if (updateItem.position.x < 0) {
        const xDiff = Math.abs(updateItem.position.x)
        parent.position.x = parent.position.x - xDiff

        if (typeof parentStyles.width === 'string') {
          const currWidth = Number(parentStyles.width.replace('px', ''))
          parentStyles.width = `${currWidth + xDiff}px`
        } else {
          parentStyles.width += xDiff
        }

        updateItem.position.x = 0
      }

      if (updateItem.position.y < 0) {
        const yDiff = Math.abs(updateItem.position.y)
        parent.position.y = parent.position.y - yDiff

        if (typeof parentStyles.height === 'string') {
          const currWidth = Number(parentStyles.height.replace('px', ''))
          parentStyles.height = `${currWidth + yDiff}px`
        } else {
          parentStyles.height += yDiff
        }

        updateItem.position.y = 0
      }

      parent.dimensions.width = Number(
        parentStyles.width.toString().replace('px', '')
      )
      parent.dimensions.height = Number(
        parentStyles.height.toString().replace('px', '')
      )

      if (typeof parent.style === 'function') {
        parent.style = (p) => {
          const styleFunc = parent.style

          return {
            ...styleFunc(p),
            ...parentStyles,
          }
        }
      } else {
        parent.style = {
          ...parent.style,
          ...parentStyles,
        }
      }
    }
  }
}

export function applyChanges(changes, elements) {
  const addRemoveChanges = changes.filter(
    (c) => c.type === 'add' || c.type === 'remove'
  )

  for (const change of addRemoveChanges) {
    if (change.type === 'add') {
      const index = elements.findIndex((el) => el.id === change.item.id)

      if (index === -1) {
        elements.push(change.item)
      }
    } else if (change.type === 'remove') {
      const index = elements.findIndex((el) => el.id === change.id)

      if (index !== -1) {
        elements.splice(index, 1)
      }
    }
  }

  const elementIds = elements.map((el) => el.id)

  for (const element of elements) {
    for (const currentChange of changes) {
      if (currentChange.id !== element.id) {
        continue
      }

      switch (currentChange.type) {
        case 'select':
          element.selected = currentChange.selected
          break
        case 'position':
          if (isGraphNode(element)) {
            if (typeof currentChange.position !== 'undefined') {
              element.position = currentChange.position
            }

            if (typeof currentChange.dragging !== 'undefined') {
              element.dragging = currentChange.dragging
            }

            if (element.expandParent && element.parentNode) {
              const parent = elements[elementIds.indexOf(element.parentNode)]

              if (parent && isGraphNode(parent)) {
                handleParentExpand(element, parent)
              }
            }
          }
          break
        case 'dimensions':
          if (isGraphNode(element)) {
            if (typeof currentChange.dimensions !== 'undefined') {
              element.dimensions = currentChange.dimensions
            }

            if (
              typeof currentChange.updateStyle !== 'undefined' &&
              currentChange.updateStyle
            ) {
              element.style = {
                ...(element.style || {}),
                width: `${currentChange.dimensions?.width}px`,
                height: `${currentChange.dimensions?.height}px`,
              }
            }

            if (typeof currentChange.resizing !== 'undefined') {
              element.resizing = currentChange.resizing
            }

            if (element.expandParent && element.parentNode) {
              const parent = elements[elementIds.indexOf(element.parentNode)]

              if (parent && isGraphNode(parent)) {
                const parentInit =
                  !!parent.dimensions.width && !!parent.dimensions.height

                if (!parentInit) {
                  nextTick(() => {
                    handleParentExpand(element, parent)
                  })
                } else {
                  handleParentExpand(element, parent)
                }
              }
            }
          }
          break
      }
    }
  }

  return elements
}

/** @deprecated Use store instance and call `applyChanges` with template-ref or the one received by `onPaneReady` instead */
export function applyEdgeChanges(changes, edges) {
  return applyChanges(changes, edges)
}

/** @deprecated Use store instance and call `applyChanges` with template-ref or the one received by `onPaneReady` instead */
export function applyNodeChanges(changes, nodes) {
  return applyChanges(changes, nodes)
}

export function createSelectionChange(id, selected) {
  return {
    id,
    type: 'select',
    selected,
  }
}

export function createAdditionChange(item) {
  return {
    item,
    type: 'add',
  }
}

export function createNodeRemoveChange(id) {
  return {
    id,
    type: 'remove',
  }
}

export function createEdgeRemoveChange(
  id,
  source,
  target,
  sourceHandle,
  targetHandle
) {
  return {
    id,
    source,
    target,
    sourceHandle: sourceHandle || null,
    targetHandle: targetHandle || null,
    type: 'remove',
  }
}

export function getSelectionChanges(
  items,
  selectedIds = new Set(),
  mutateItem = false
) {
  const changes = []

  for (const [id, item] of items) {
    const willBeSelected = selectedIds.has(id)

    // we don't want to set all items to selected=false on the first selection
    if (
      !(item.selected === undefined && !willBeSelected) &&
      item.selected !== willBeSelected
    ) {
      if (mutateItem) {
        // this hack is needed for nodes. When the user dragged a node, it's selected.
        // When another node gets dragged, we need to deselect the previous one,
        // in order to have only one selected node at a time - the onNodesChange callback comes too late here :/
        item.selected = willBeSelected
      }
      changes.push(createSelectionChange(item.id, willBeSelected))
    }
  }

  return changes
}
