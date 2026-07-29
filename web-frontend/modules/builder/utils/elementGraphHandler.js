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
    return super.getChildren(targetElement, {
      followChains: true,
      skipMissing: true,
    })
  }

  // Returns the chain of children in a specific container slot.
  getChildrenInPlace(containerElement, place) {
    return super.getChildren(containerElement, {
      slot: place,
      followChains: true,
      skipMissing: true,
    })
  }

  // Returns elements following this element on the default next edge.
  getNextElements(targetElement) {
    return this.getNextPoints(targetElement, '')
  }

  // Depth-first ordered flat list of all elements.
  getOrderedElements() {
    const result = this.getPointsInDepthFirstOrder({
      skipMissing: true,
      skipChildrenOfMissing: true,
    })

    // Elements that exist on the page but aren't present in the graph (e.g. records
    // created during a not-yet-zero-downtime deployment) are appended at the bottom
    // so they stay visible and editable rather than silently disappearing.
    const orderedIds = new Set(result.map((el) => `${el.id}`))
    const elementMap = this.getPointMap()
    for (const id of Object.keys(elementMap)) {
      if (!orderedIds.has(id)) {
        result.push(elementMap[id])
      }
    }

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
    // A corrupted graph can contain self-references (a point whose next or
    // child is itself) or cycles; track the walked points so the chain walk
    // always terminates instead of hanging the page.
    const seen = new Set()
    for (const [nodeId, info] of Object.entries(graph)) {
      if (nodeId === '0' || !info || typeof info !== 'object') continue
      const children = info.children
      if (!children) continue
      const childrenObj = Array.isArray(children) ? { '': children } : children
      for (const [place, headIds] of Object.entries(childrenObj)) {
        let currentId = headIds[0] ?? null
        while (
          currentId != null &&
          Number(currentId) !== Number(nodeId) &&
          !seen.has(Number(currentId))
        ) {
          seen.add(Number(currentId))
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
