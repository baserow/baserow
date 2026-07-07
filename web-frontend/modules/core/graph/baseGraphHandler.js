import { clone } from '@baserow/modules/core/utils/object'

const replace = (array, itemToReplace, replacement) => {
  const foundIndex = array.findIndex((item) => item === itemToReplace)
  return [
    ...array.slice(0, foundIndex),
    ...(Array.isArray(replacement) ? replacement : [replacement]),
    ...array.slice(foundIndex + 1),
  ]
}

export default class BaseGraphHandler {
  constructor(container) {
    this.container = container
    this.graph = clone(container.graph || {})
  }

  getPointMap() {
    throw new Error('getPointMap() must be implemented by subclass')
  }

  getPoint(pointId) {
    return this.getPointMap()[pointId] || null
  }

  getInfo(point) {
    const id = point?.id ?? point
    return this.graph[id]
  }

  // Returns a flat array of child IDs, handling both the legacy array format
  // [id, ...] and the new dict format {"slot": [id, ...]}.
  _getChildrenIds(info) {
    const children = info?.children
    if (!children) return []
    if (Array.isArray(children)) return children
    return Object.values(children).flat()
  }

  // Normalises children to dict format. Legacy flat arrays become {"": [...]}.
  _getChildrenAsDict(children) {
    if (!children) return {}
    if (Array.isArray(children)) return { '': children }
    return children
  }

  hasPoints() {
    return Boolean(this.getFirstPoint())
  }

  getFirstPoint() {
    if (this.graph['0']) {
      return this.getPoint(this.graph['0'])
    }
    return null
  }

  // Returns children of targetPoint.
  // slot: restrict to a specific slot/place; null means all slots.
  // followChains: if true, follows next[''] chains within each slot (builder style);
  //   if false, returns only the head of each slot (automation style).
  // skipMissing: if true, missing points are skipped while traversal continues
  //   along the default next chain.
  getChildren(
    targetPoint,
    { slot = null, followChains = false, skipMissing = false } = {}
  ) {
    const childrenDict = this._getChildrenAsDict(
      this.getInfo(targetPoint)?.children
    )
    const slotEntries =
      slot !== null
        ? [[slot, childrenDict[slot] || []]]
        : Object.entries(childrenDict)

    const result = []
    for (const [, headIds] of slotEntries) {
      if (!headIds.length) continue
      if (!followChains) {
        const point = this.getPoint(headIds[0])
        if (point) result.push(point)
      } else {
        let currentId = headIds[0]
        while (currentId) {
          const point = this.getPoint(currentId)
          if (!point && !skipMissing) break
          if (point) result.push(point)
          currentId = this.graph[currentId]?.next?.['']?.[0] ?? null
        }
      }
    }
    return result
  }

  getNextPoints(targetPoint, output = null) {
    const next = this.getInfo(targetPoint)?.next
    if (!next) return []

    return Object.entries(next)
      .filter(
        ([uid, pointIds]) =>
          pointIds.length && (output === null || uid === output)
      )
      .map(([, pointIds]) => pointIds)
      .flat()
      .map((id) => this.getPoint(id))
      .filter((point) => point)
  }

  getPointsInDepthFirstOrder({
    skipMissing = false,
    skipChildrenOfMissing = false,
  } = {}) {
    const result = []
    const visited = new Set()

    const visitChain = (firstId) => {
      let currentId = firstId
      while (currentId && !visited.has(currentId)) {
        visited.add(currentId)
        const point = this.getPoint(currentId)
        if (!point && !skipMissing) break

        const info = this.graph[currentId]
        if (!info) break

        if (point) {
          result.push(point)
        }

        if (info.children && (point || !skipChildrenOfMissing)) {
          const childrenDict = this._getChildrenAsDict(info.children)
          for (const slot of Object.keys(childrenDict).sort()) {
            const firstChildId = childrenDict[slot]?.[0]
            if (firstChildId) visitChain(firstChildId)
          }
        }

        currentId = info.next?.['']?.[0] ?? null
      }
    }

    if (this.graph['0']) visitChain(this.graph['0'])

    return result
  }

  getPointAtPosition(referencePoint, position, output) {
    output = String(output)

    switch (position) {
      case 'south':
        if (referencePoint === null) {
          return this.getPoint(this.graph['0'])
        }
        {
          const nextIds = this.getInfo(referencePoint)?.next?.[output] || []
          if (nextIds.length > 0) return this.getPoint(nextIds[0])
        }
        break

      case 'child': {
        const childrenDict = this._getChildrenAsDict(
          this.getInfo(referencePoint)?.children
        )
        const childIds = childrenDict[output] || []
        if (childIds.length > 0) return this.getPoint(childIds[0])
        break
      }

      default:
        throw new Error(`Unexpected position: ${position}`)
    }
    return null
  }

  getPreviousPositions(target) {
    const explore = (currentPosition, path) => {
      const point = this.getPointAtPosition(...currentPosition)
      if (point === null) return null

      const pointId = String(point.id)
      if (pointId === String(target.id)) return path

      const info = this.getInfo(pointId)
      const nextPositions = []

      if (info?.next) {
        for (const uid of Object.keys(info.next)) {
          if (info.next[uid]?.length) {
            nextPositions.push([pointId, 'south', uid])
          }
        }
      }

      if (info?.children) {
        const childrenDict = this._getChildrenAsDict(info.children)
        for (const [slot, childIds] of Object.entries(childrenDict)) {
          if (childIds?.length) {
            nextPositions.push([pointId, 'child', slot])
          }
        }
      }

      for (const nextPos of nextPositions) {
        const found = explore(nextPos, [...path, nextPos])
        if (found !== null && found !== undefined) return found
      }

      return null
    }

    const result = explore([null, 'south', ''], [])
    if (!result) return []
    return result.map(([nid, p, o]) => [this.getPoint(nid), p, o])
  }

  getPointPosition(point) {
    if (this.graph['0'] === point.id) {
      return [null, 'south', '']
    }
    for (const [pointId, value] of Object.entries(this.graph)) {
      if (!value || typeof value !== 'object') continue

      if (value.next) {
        const outputFound = Object.entries(value.next).find(([, nextOnEdge]) =>
          nextOnEdge.includes(point.id)
        )
        if (outputFound) {
          return [this.getPoint(pointId), 'south', outputFound[0]]
        }
      }

      if (value.children) {
        const childrenDict = this._getChildrenAsDict(value.children)
        for (const [slot, childIds] of Object.entries(childrenDict)) {
          if (childIds?.includes(point.id)) {
            return [this.getPoint(pointId), 'child', slot]
          }
        }
      }
    }
    throw new Error(`Point ${point.id} not found in graph`)
  }

  insert(point, referencePoint, position, output) {
    if (position === 'north') {
      const [prevRef, prevPos, prevOutput] =
        this.getPointPosition(referencePoint)
      this._insertAt(point, prevRef, prevPos, prevOutput)
      return
    }

    this._insertAt(point, referencePoint, position, output)
  }

  append(point) {
    const [lastRef, lastPos, lastOutput] = this.getLastPosition()
    this._insertAt(point, lastRef, lastPos, lastOutput)
  }

  _insertAt(point, referencePoint, position, output) {
    // A null/undefined output means the default '' edge — never a literal
    // 'null'/'undefined' slot key (mirrors the backend's None guard).
    output = output == null ? '' : String(output)

    if (!referencePoint) {
      let next = null
      if (this.graph['0']) {
        next = [this.graph['0']]
      }
      this.graph['0'] = point.id
      this.graph[point.id] = next ? { next: { '': next } } : {}
      return
    }

    let newPointNext

    switch (position) {
      case 'south': {
        if (!this.graph[referencePoint.id].next) {
          this.graph[referencePoint.id].next = {}
        }
        if (!this.graph[referencePoint.id].next[output]) {
          this.graph[referencePoint.id].next[output] = []
        }
        newPointNext = this.graph[referencePoint.id].next[output]
        this.graph[referencePoint.id].next[output] = [point.id]
        break
      }

      case 'child': {
        const refInfo = this.graph[referencePoint.id]
        // Normalise legacy bare-array children to dict form *before* mutating.
        // Otherwise we'd bolt an `output` string key onto the array while the
        // existing children stay at numeric indices, losing them and leaving
        // newPointNext empty (the reported "child vanishes" bug).
        const childrenDict = this._getChildrenAsDict(refInfo.children)
        refInfo.children = childrenDict
        if (!childrenDict[output]) {
          childrenDict[output] = []
        }
        newPointNext = childrenDict[output]
        childrenDict[output] = [point.id]
        break
      }

      default:
        throw new Error(`Unexpected position: ${position}`)
    }

    this.graph[point.id] = {
      next: { '': newPointNext },
    }
  }

  // Delete pointId plus every node reachable by following its `next` chain AND
  // recursing into each node's `children`. Used when cascading into a container slot.
  _deleteChainAndDescendants(pointId) {
    let currentId = pointId
    while (currentId) {
      const info = this.graph[currentId]
      if (!info || typeof info !== 'object') break

      const allNextIds = Object.values(info.next || {}).flat()
      const childrenDict = this._getChildrenAsDict(info.children)

      for (const firstChildIds of Object.values(childrenDict)) {
        for (const cid of firstChildIds) {
          this._deleteChainAndDescendants(cid)
        }
      }

      delete this.graph[currentId]

      // Follow default next; handle other outputs (automation routing) recursively.
      currentId = allNextIds[0] ?? null
      for (const nid of allNextIds.slice(1)) {
        this._deleteChainAndDescendants(nid)
      }
    }
  }

  // Delete pointId's graph entry and all its descendants (children chains).
  // Does NOT follow the point's own `next` edges — those are siblings handled
  // by remove() before this is called.
  _deleteDescendantGraphEntries(pointId) {
    const info = this.graph[pointId]
    if (!info || typeof info !== 'object') return

    const childrenDict = this._getChildrenAsDict(info.children)
    for (const firstChildIds of Object.values(childrenDict)) {
      for (const cid of firstChildIds) {
        this._deleteChainAndDescendants(cid)
      }
    }

    delete this.graph[pointId]
  }

  // Collect the IDs of every descendant of pointId (direct and transitive),
  // following next[''] chains within each slot and recursing into each child.
  getDescendantIds(pointId) {
    const result = []
    const info = this.graph[pointId]
    if (!info || typeof info !== 'object') return result
    const childrenDict = this._getChildrenAsDict(info.children)
    for (const headIds of Object.values(childrenDict)) {
      for (const cid of headIds) {
        this._collectChainAndDescendants(cid, result)
      }
    }
    return result
  }

  _collectChainAndDescendants(pointId, acc) {
    let currentId = pointId
    while (currentId != null) {
      const info = this.graph[currentId]
      if (!info || typeof info !== 'object') break
      acc.push(currentId)
      const childrenDict = this._getChildrenAsDict(info.children)
      for (const headIds of Object.values(childrenDict)) {
        for (const cid of headIds) {
          this._collectChainAndDescendants(cid, acc)
        }
      }
      const allNext = Object.values(info.next || {}).flat()
      currentId = allNext[0] ?? null
      for (const nid of allNext.slice(1)) {
        this._collectChainAndDescendants(nid, acc)
      }
    }
  }

  // Returns the descendant points (records) of the given point.
  getDescendants(point) {
    const id = point?.id ?? point
    return this.getDescendantIds(id)
      .map((pid) => this.getPoint(pid))
      .filter((p) => p)
  }

  // keepDescendants: when true, the point's own graph entry is deleted but its
  // subtree entries are NOT removed (used by move() to re-attach the subtree).
  remove(point, { keepDescendants = false } = {}) {
    const [previousRef, position, output] = this.getPointPosition(point)

    const pointInfo = this.graph[point.id]
    const previousRefInfo = previousRef ? this.graph[previousRef.id] : null

    switch (position) {
      case 'south':
        if (previousRefInfo) {
          previousRefInfo.next[output] = replace(
            previousRefInfo.next[output],
            point.id,
            Object.values(pointInfo.next || {}).flat()
          )
        } else if (this.graph[point.id]?.next?.['']) {
          this.graph['0'] = this.graph[point.id].next[''][0]
        } else {
          delete this.graph['0']
        }
        break

      case 'child': {
        if (!previousRefInfo.children) {
          previousRefInfo.children = {}
        }
        const childrenDict = this._getChildrenAsDict(previousRefInfo.children)
        childrenDict[output] = replace(
          childrenDict[output] || [],
          point.id,
          Object.values(pointInfo.next || {}).flat()
        )
        previousRefInfo.children = childrenDict
        break
      }

      default:
        throw new Error(`Unexpected position: ${position}`)
    }

    if (keepDescendants) {
      delete this.graph[point.id]
    } else {
      this._deleteDescendantGraphEntries(point.id)
    }
  }

  getLastPosition() {
    if (!this.graph['0']) return [null, 'south', '']

    const searchLast = (pointId) => {
      const next = this.graph[pointId]?.next?.[''] ?? []
      if (!next.length) return [this.getPoint(pointId), 'south', '']
      return searchLast(next[0])
    }

    return searchLast(this.graph['0'])
  }

  // When targetHandler is supplied (and differs from this handler) the point is
  // moved across graphs: its whole subtree (children + descendants) is migrated
  // into the target graph and removed from this (source) one. Its `next` (old
  // siblings) is NOT carried — insert() sets the new one.
  move(pointToMove, referencePoint, position, output, targetHandler = null) {
    // Moving a point relative to itself is a no-op. Without this guard remove()
    // would delete the point's graph entry before insert() tries to reference it,
    // throwing "Cannot read properties of undefined".
    if (referencePoint && referencePoint.id === pointToMove.id) {
      return
    }

    const target = targetHandler || this
    const isCrossGraph = target !== this

    // An orphaned point (present in the point map but absent from the graph, e.g.
    // created during a not-yet-zero-downtime deployment) has no graph entry yet.
    // Moving it makes it *join* the graph as a fresh insert: there are no previous
    // children to preserve and nothing to remove from the source graph.
    const existingEntry = this.graph[pointToMove.id]
    const previousChildren = existingEntry?.children

    let migratedDescendants = null
    if (isCrossGraph && existingEntry) {
      migratedDescendants = this.getDescendantIds(pointToMove.id).map((id) => [
        id,
        clone(this.graph[id]),
      ])
    }

    // Same-graph: keep descendants in place and just relink the point.
    // Cross-graph: cascade-remove the subtree from the source graph.
    // Orphan: nothing to remove — it isn't in the source graph yet.
    if (existingEntry) {
      this.remove(pointToMove, { keepDescendants: !isCrossGraph })
    }

    if (isCrossGraph && migratedDescendants) {
      for (const [id, entry] of migratedDescendants) {
        target.graph[id] = entry
      }
    }

    if (referencePoint === null && position === 'south') {
      // null reference + south = append to end of the chain.
      // _insertAt(null, ...) always places at root (first), so use getLastPosition instead.
      const [lastRef, lastPos, lastOutput] = target.getLastPosition()
      target._insertAt(pointToMove, lastRef, lastPos, lastOutput)
    } else {
      target.insert(pointToMove, referencePoint, position, output)
    }

    target.graph[pointToMove.id].children = previousChildren
  }

  replace(pointToReplace, newPoint) {
    const [referencePoint, position, output] =
      this.getPointPosition(pointToReplace)

    this.remove(pointToReplace)
    this.insert(newPoint, referencePoint, position, output)
  }
}
