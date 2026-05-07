import BigNumber from 'bignumber.js'
import BaseGraphHandler from '@baserow/modules/core/graph/baseGraphHandler'

export default class ElementGraphHandler extends BaseGraphHandler {
  constructor(page) {
    super(page)
  }

  getPointMap() {
    return this.container.elementMap
  }

  getElement(elementId) {
    return this.getPoint(elementId)
  }

  hasElements() {
    return this.hasPoints()
  }

  getFirstElement() {
    return this.getFirstPoint()
  }

  getElementAtPosition(referenceElement, position, output) {
    return this.getPointAtPosition(referenceElement, position, output)
  }

  getElementPosition(element) {
    return this.getPointPosition(element)
  }

  // Follows next[''] chains within each slot (all children at every depth within slots).
  getChildren(targetElement) {
    return super.getChildren(targetElement, { followChains: true })
  }

  // Returns the chain of children in a specific container slot.
  getChildrenInPlace(containerElement, place) {
    return super.getChildren(containerElement, {
      slot: place,
      followChains: true,
    })
  }

  // Returns elements following this element on the default next edge.
  getNextElements(targetElement) {
    const next = this.getInfo(targetElement)?.next?.['']
    if (!next?.length) return []
    return next.map((id) => this.getElement(id)).filter((el) => el)
  }

  // Depth-first ordered flat list of all elements.
  getOrderedElements() {
    const result = []
    const visited = new Set()

    const visitChain = (firstId) => {
      let currentId = firstId
      while (currentId && !visited.has(currentId)) {
        visited.add(currentId)
        const el = this.getElement(currentId)
        if (el) result.push(el)
        const info = this.graph[currentId]
        if (!info) break

        if (info.children) {
          for (const place of Object.keys(info.children).sort()) {
            const firstChildId = (info.children[place] || [])[0]
            if (firstChildId) visitChain(firstChildId)
          }
        }

        currentId = info.next?.['']?.[0] ?? null
      }
    }

    if (this.graph['0']) visitChain(this.graph['0'])
    return result
  }

  /**
   * Builds { parentMap, placeMap } by walking every children entry in the graph
   * and following the next[''] chain within each slot.
   *
   * parentMap: { elementId (number) -> parentId (number) }
   * placeMap:  { elementId (number) -> place_in_container (string) }
   *
   * Elements not inside any container are absent from both maps.
   */
  static buildElementMaps(graph) {
    const parentMap = {}
    const placeMap = {}
    for (const [nodeId, info] of Object.entries(graph)) {
      if (nodeId === '0' || !info || typeof info !== 'object') continue
      const children = info.children
      if (!children) continue
      const childrenObj = Array.isArray(children) ? { '': children } : children
      for (const [place, headIds] of Object.entries(childrenObj)) {
        let currentId = headIds[0] ?? null
        while (currentId) {
          const id = Number(currentId)
          parentMap[id] = Number(nodeId)
          placeMap[id] = place
          const nextIds = graph[String(currentId)]?.next?.['']
          currentId = nextIds?.[0] ?? null
        }
      }
    }
    return { parentMap, placeMap }
  }

  /**
   * Reconstructs a graph from compat fields (parent_element_id,
   * place_in_container, order). Used after initial fetch, duplicate, and
   * realtime events.
   *
   * Edge case: if an element's parent_element_id references an element not
   * present in the set (e.g. during a deployment window), it is treated as a
   * root element appended at the end of the page.
   */
  static buildGraphFromElements(elements) {
    if (!elements || elements.length === 0) return {}

    const elementIds = new Set(elements.map((el) => el.id))
    const graph = {}
    const groups = {}

    elements.forEach((el) => {
      graph[el.id] = {}
      const parentId =
        el.parent_element_id && elementIds.has(el.parent_element_id)
          ? el.parent_element_id
          : null
      const place = el.place_in_container ?? ''
      const key = `${parentId}:${place}`
      if (!groups[key]) groups[key] = []
      groups[key].push(el)
    })

    Object.values(groups).forEach((group) => {
      group.sort((a, b) => {
        const orderA = a.order ? new BigNumber(a.order) : new BigNumber(0)
        const orderB = b.order ? new BigNumber(b.order) : new BigNumber(0)
        return orderA.comparedTo(orderB)
      })
    })

    // Process null-parent (root) groups first, then nested.
    const sortedKeys = Object.keys(groups).sort((a) =>
      a.startsWith('null:') ? -1 : 1
    )

    sortedKeys.forEach((key) => {
      const group = groups[key]
      const colonIndex = key.indexOf(':')
      const parentStr = key.slice(0, colonIndex)
      const place = key.slice(colonIndex + 1)
      const parentId = parentStr === 'null' ? null : Number(parentStr)

      // Chain elements within the group via next[""]
      for (let i = 0; i < group.length - 1; i++) {
        if (!graph[group[i].id]) graph[group[i].id] = {}
        graph[group[i].id].next = { '': [group[i + 1].id] }
      }

      if (parentId === null) {
        if (!graph['0']) {
          // First root group sets graph['0']
          if (group.length > 0) graph['0'] = group[0].id
        } else {
          // Subsequent root groups (orphaned elements) appended at end
          let lastId = graph['0']
          while (graph[lastId]?.next?.['']?.[0]) {
            lastId = graph[lastId].next[''][0]
          }
          if (group.length > 0) {
            if (!graph[lastId]) graph[lastId] = {}
            graph[lastId].next = { '': [group[0].id] }
          }
        }
      } else {
        if (group.length > 0 && graph[parentId] !== undefined) {
          if (!graph[parentId].children) graph[parentId].children = {}
          graph[parentId].children[place] = [group[0].id]
        }
      }
    })

    return graph
  }
}
