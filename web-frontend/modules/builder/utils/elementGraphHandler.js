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
    return this.getNextPoints(targetElement, '')
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
}
