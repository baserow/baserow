import { clone } from '@baserow/modules/core/utils/object'
import { uuid } from '@baserow/modules/core/utils/string'

import ElementService from '@baserow/modules/builder/services/element'
import PublicBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import ElementGraphHandler from '@baserow/modules/builder/utils/elementGraphHandler'

const populateElement = (element, registry) => {
  const elementType = registry.get('element', element.type)
  element._ = {
    contentLoading: true,
    content: [],
    hasNextPage: true,
    reset: 0,
    shouldBeFocused: false,
    elementNamespacePath: null,
    // This uid ensure that when we refresh the elements from the server when we
    // authenticate that it didn't reuse some of the store values
    // It breaks collection element reload after authentication for instance
    // This uid is used as key in the PageElement component
    uid: uuid(),
    ...elementType.getPopulateStoreProperties(),
  }

  return element
}

const state = {}

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
  valuesToUpdate: {},
  moveTimeout: null,
}

const updateCachedValues = (page) => {
  page.elementMap = Object.fromEntries(
    page.elements.map((element) => [`${element.id}`, element])
  )
  // Derive place_in_container and parent from the graph (graph is authoritative)
  const { parentMap, placeMap } = ElementGraphHandler.buildElementMaps(
    page.graph || {}
  )
  page.parentMap = parentMap
  for (const element of page.elements) {
    element.place_in_container = placeMap[element.id] ?? ''
  }
  page.orderedElements = new ElementGraphHandler(page).getOrderedElements()
}

const mutations = {
  SET_ITEMS(state, { builder, page, elements }) {
    const { $registry } = this
    builder.selectedElement = null
    page.elements = elements.map((element) =>
      populateElement(element, $registry)
    )
    updateCachedValues(page)
  },
  ADD_ITEM(state, { page, element, sourcePageId = null }) {
    const { $registry } = this
    const isSamePageMove = sourcePageId !== null && sourcePageId === page.id
    const existingContentState = isSamePageMove ? element._ : null
    page.elements.push(populateElement(element, $registry))
    if (existingContentState) {
      element._.content = existingContentState.content
      element._.hasNextPage = existingContentState.hasNextPage
      element._.contentLoading = false
    }
    updateCachedValues(page)
  },
  UPDATE_ITEM(state, { builder, page, element: elementToUpdate, values }) {
    let updateCached = false
    page.elements.forEach((element) => {
      if (element.id === elementToUpdate.id) {
        if (
          values.place_in_container !== undefined &&
          values.place_in_container !== element.place_in_container
        ) {
          updateCached = true
        }
        Object.assign(element, values)
      }
    })
    if (builder.selectedElement?.id === elementToUpdate.id) {
      Object.assign(builder.selectedElement, values)
    }
    if (updateCached) {
      updateCachedValues(page)
    }
  },
  DELETE_ITEM(state, { page, elementId }) {
    const index = page.elements.findIndex((element) => element.id === elementId)
    if (index > -1) {
      page.elements.splice(index, 1)
    }
    updateCachedValues(page)
  },
  SELECT_ITEM(state, { builder, element }) {
    builder.selectedElement = element
  },
  CLEAR_ITEMS(state, { page }) {
    page.elements = []
    page.graph = {}
    updateCachedValues(page)
  },
  _SET_ELEMENT_NAMESPACE_PATH(state, { element, path }) {
    element._.elementNamespacePath = path
  },
}

const actions = {
  clearAll({ commit }, { page }) {
    commit('CLEAR_ITEMS', { page })
  },
  forceCreate({ dispatch, commit }, { page, element }) {
    const { $registry } = this
    commit('ADD_ITEM', { page, element })
    dispatch('_setElementNamespacePath', { page, element })

    const elementType = $registry.get('element', element.type)
    elementType.afterCreate(element, page)

    // If the element is not yet in the graph, append it to the end of the root
    // chain. This handles test setup and compat-field-based callers that do not
    // supply explicit graph position parameters. The undo path is exempt: it
    // restores page.graph via page/forceUpdate before calling forceCreate, so
    // the element is already present in the graph.
    if (!(String(element.id) in (page.graph || {}))) {
      dispatch('graphInsert', {
        page,
        element,
        referenceElement: null,
        position: 'south',
        output: '',
      })
    }
  },
  forceUpdate({ commit }, { builder, page, element, values }) {
    const { $registry } = this
    commit('UPDATE_ITEM', { builder, page, element, values })
    const elementType = $registry.get('element', element.type)
    elementType.afterUpdate(element, page)
  },
  forceDelete({ commit, getters }, { builder, page, elementId }) {
    const { $registry } = this
    const elementToDelete = getters.getElementById(page, elementId)

    if (getters.getSelected(builder)?.id === elementId) {
      commit('SELECT_ITEM', { builder, element: null })
    }
    commit('DELETE_ITEM', { page, elementId })

    const elementType = $registry.get('element', elementToDelete.type)
    elementType.afterDelete(elementToDelete, page)
  },
  graphInsert(
    { dispatch },
    { page, element, referenceElement, position, output }
  ) {
    const handler = new ElementGraphHandler(page)
    if (referenceElement === null && position === 'south') {
      // No reference + south = append to end, matching backend service behaviour.
      // handler.insert(null, 'south') would place at root (first) instead.
      handler.append(element)
    } else {
      handler.insert(element, referenceElement, position, output)
    }
    dispatch(
      'page/forceUpdate',
      { page, values: { graph: handler.graph } },
      {
        root: true,
      }
    )
    updateCachedValues(page)
  },
  graphRemove({ dispatch }, { page, element }) {
    const handler = new ElementGraphHandler(page)
    handler.remove(element)
    dispatch(
      'page/forceUpdate',
      { page, values: { graph: handler.graph } },
      {
        root: true,
      }
    )
    updateCachedValues(page)
  },
  graphMove(
    { dispatch },
    { page, elementToMove, referenceElement, position, output }
  ) {
    const handler = new ElementGraphHandler(page)
    handler.move(elementToMove, referenceElement, position, output)
    dispatch(
      'page/forceUpdate',
      { page, values: { graph: handler.graph } },
      {
        root: true,
      }
    )
    updateCachedValues(page)
  },
  graphReplace({ dispatch }, { page, elementToReplace, newElement }) {
    const handler = new ElementGraphHandler(page)
    handler.replace(elementToReplace, newElement)
    dispatch(
      'page/forceUpdate',
      { page, values: { graph: handler.graph } },
      {
        root: true,
      }
    )
    updateCachedValues(page)
  },
  select({ commit }, { builder, element }) {
    updateContext.lastUpdatedValues = null
    commit('SELECT_ITEM', { builder, element })
  },
  async create(
    { dispatch, commit, getters },
    {
      builder,
      page,
      elementType: elementTypeName,
      referenceElementId = null,
      position = 'south',
      placeInContainer = '',
      values = null,
      forceCreate = true,
    }
  ) {
    const { $registry, $client } = this
    const elementType = $registry.get('element', elementTypeName)

    const referenceElement = referenceElementId
      ? getters.getElementById(page, referenceElementId)
      : null

    let parentElement = null
    if (referenceElement) {
      parentElement =
        position === 'child'
          ? referenceElement
          : getters.getParent(page, referenceElement)
    }

    const updatedValues = elementType.getDefaultValues(
      page,
      values,
      parentElement
    )

    // Placeholder used only for graph bookkeeping — never stored in page.elements
    // so we never render an element with incomplete field data while in-flight.
    const tempElement = { id: uuid() }
    const initialGraph = clone(page.graph)

    dispatch('graphInsert', {
      page,
      element: tempElement,
      referenceElement,
      position,
      output: placeInContainer,
    })

    try {
      const { data: element } = await ElementService($client).create(
        page.id,
        elementTypeName,
        referenceElementId,
        position,
        placeInContainer,
        updatedValues
      )

      commit('ADD_ITEM', { page, element })

      dispatch('graphReplace', {
        page,
        elementToReplace: tempElement,
        newElement: element,
      })

      if (forceCreate) {
        await dispatch('forceCreate', { page, element })
        await dispatch('application/refreshPermissions', builder, { root: true })

        await dispatch('select', { builder, element })
      }

      return element
    } catch (error) {
      dispatch(
        'page/forceUpdate',
        { page, values: { graph: initialGraph } },
        { root: true }
      )
      throw error
    }
  },
  async update({ dispatch }, { builder, page, element, values }) {
    const { $client } = this
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(element, name)) {
        oldValues[name] = element[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', { builder, page, element, values: newValues })

    try {
      await ElementService($client).update(element.id, values)
    } catch (error) {
      await dispatch('forceUpdate', {
        builder,
        page,
        element,
        values: oldValues,
      })
      throw error
    }
  },

  async debouncedUpdate(
    { dispatch, getters },
    { builder, page, element, values }
  ) {
    const { $client } = this
    const oldValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(element, name)) {
        oldValues[name] = element[name]
        updateContext.valuesToUpdate[name] = values[name]
      }
    })

    await dispatch('forceUpdate', {
      builder,
      page,
      element,
      values: updateContext.valuesToUpdate,
    })

    return new Promise((resolve, reject) => {
      const fire = async () => {
        const toUpdate = updateContext.valuesToUpdate
        updateContext.valuesToUpdate = {}
        try {
          await ElementService($client).update(element.id, toUpdate)
          updateContext.lastUpdatedValues = null
          resolve()
        } catch (error) {
          if (updateContext.lastUpdatedValues) {
            await dispatch('forceUpdate', {
              builder,
              page,
              element,
              values: updateContext.lastUpdatedValues,
            })
          }
          updateContext.lastUpdatedValues = null
          reject(error)
        }
      }

      if (updateContext.promiseResolve) {
        updateContext.promiseResolve()
        updateContext.promiseResolve = null
      }

      clearTimeout(updateContext.updateTimeout)

      if (!updateContext.lastUpdatedValues) {
        updateContext.lastUpdatedValues = oldValues
      }

      updateContext.updateTimeout = setTimeout(fire, 500)
      updateContext.promiseResolve = resolve
    })
  },
  async delete({ dispatch, commit, getters }, { builder, page, elementId }) {
    const { $client } = this
    const elementToDelete = getters.getElementById(page, elementId)
    const descendants = getters.getDescendants(page, elementToDelete)

    const initialGraph = clone(page.graph)

    dispatch('graphRemove', { page, element: elementToDelete })

    if (getters.getSelected(builder)?.id === elementId) {
      commit('SELECT_ITEM', { builder, element: null })
    }

    // Remove the element and all its descendants from the local element list.
    descendants.forEach((descendant) => {
      commit('DELETE_ITEM', { page, elementId: descendant.id })
    })
    commit('DELETE_ITEM', { page, elementId })

    try {
      await ElementService($client).delete(elementId)
    } catch (error) {
      dispatch(
        'page/forceUpdate',
        { page, values: { graph: initialGraph } },
        {
          root: true,
        }
      )
      await dispatch('forceCreate', { page, element: elementToDelete })
      await Promise.all(
        descendants.map((descendant) =>
          dispatch('forceCreate', { page, element: descendant })
        )
      )
      throw error
    }
  },
  async fetch({ dispatch, commit }, { builder, page }) {
    const { $client } = this
    const { data: elements } = await ElementService($client).fetchAll(page.id)

    commit('SET_ITEMS', { builder, page, elements })

    await Promise.all(
      elements.map((element) =>
        dispatch('_setElementNamespacePath', { page, element })
      )
    )

    return elements
  },
  async fetchPublished({ dispatch, commit }, { builder, page }) {
    const { $client } = this
    const { data: elements } =
      await PublicBuilderService($client).fetchElements(page)

    commit('SET_ITEMS', { builder, page, elements })

    await Promise.all(
      elements.map((element) =>
        dispatch('_setElementNamespacePath', { page, element })
      )
    )

    return elements
  },
  async move(
    { commit, dispatch, getters },
    {
      builder,
      page,
      elementId,
      referenceElementId,
      position,
      placeInContainer = '',
      targetPage = null,
    }
  ) {
    const { $client, $registry } = this
    const element = getters.getElementById(page, elementId)
    const resolvedTargetPage = targetPage !== null ? targetPage : page
    const isCrossPage = targetPage !== null && targetPage.id !== page.id

    const referenceElement = referenceElementId
      ? (getters.getElementById(resolvedTargetPage, referenceElementId) ??
        getters.getElementById(page, referenceElementId))
      : null

    const initialSourceGraph = clone(page.graph)
    const initialTargetGraph = isCrossPage
      ? clone(resolvedTargetPage.graph)
      : null

    // For a cross-page move the whole subtree (the element AND its descendants)
    // relocates. Capture it (root first) and pre-compute the resulting graphs.
    // wrapMove relocates each record via forceCreate, which would otherwise
    // append the children at the target root (they aren't in the target graph
    // yet → "unfurled"); we overwrite the graphs with the correct result below.
    let subtreeElements = [element]
    let finalSourceGraph = null
    let finalTargetGraph = null
    if (isCrossPage) {
      const sourceHandler = new ElementGraphHandler(page)
      subtreeElements = [element, ...sourceHandler.getDescendants(element)]

      const targetHandler = new ElementGraphHandler(resolvedTargetPage)
      sourceHandler.move(
        element,
        referenceElement,
        position ?? 'south',
        placeInContainer ?? '',
        targetHandler
      )
      finalSourceGraph = sourceHandler.graph
      finalTargetGraph = targetHandler.graph
    }

    const elementType = $registry.get('element', element.type)

    elementType.wrapMove(
      {
        builder,
        previousPage: page,
        page: resolvedTargetPage,
        element,
      },
      () => {
        if (isCrossPage) {
          // wrapMove already relocated the descendant records; relocate the root
          // record here. The graphs are corrected once below.
          commit('DELETE_ITEM', { page, elementId: element.id })
          commit('ADD_ITEM', {
            page: resolvedTargetPage,
            sourcePageId: page.id,
            element: { ...element, page_id: resolvedTargetPage.id },
          })
          dispatch('_setElementNamespacePath', {
            page: resolvedTargetPage,
            element: getters.getElementById(resolvedTargetPage, elementId),
          })
        } else {
          // Same-page: optimistic graph move.
          dispatch('graphMove', {
            page,
            elementToMove: element,
            referenceElement,
            position,
            output: placeInContainer,
          })
        }
      }
    )

    if (isCrossPage) {
      // Overwrite both graphs with the subtree-aware result, replacing the
      // transient root-level entries forceCreate produced during wrapMove.
      dispatch(
        'page/forceUpdate',
        { page, values: { graph: finalSourceGraph } },
        { root: true }
      )
      dispatch(
        'page/forceUpdate',
        { page: resolvedTargetPage, values: { graph: finalTargetGraph } },
        { root: true }
      )
      updateCachedValues(page)
      updateCachedValues(resolvedTargetPage)
    }

    const fire = async () => {
      try {
        const { data: elementUpdated } = await ElementService($client).move(
          elementId,
          referenceElementId,
          position,
          placeInContainer,
          targetPage?.id ?? null
        )

        dispatch('forceUpdate', {
          builder,
          page: resolvedTargetPage,
          element: elementUpdated,
          values: {
            page_id: elementUpdated.page_id,
          },
        })

        if (isCrossPage) {
          // The optimistic graph already matches the confirmed move (identical
          // params); re-apply it defensively in case forceUpdate disturbed it.
          dispatch(
            'page/forceUpdate',
            { page: resolvedTargetPage, values: { graph: finalTargetGraph } },
            { root: true }
          )
          updateCachedValues(resolvedTargetPage)
        }
      } catch (error) {
        // Restore source graph
        dispatch(
          'page/forceUpdate',
          { page, values: { graph: initialSourceGraph } },
          { root: true }
        )
        updateCachedValues(page)

        if (isCrossPage) {
          // Restore target graph and move the whole subtree back to the source.
          dispatch(
            'page/forceUpdate',
            { page: resolvedTargetPage, values: { graph: initialTargetGraph } },
            { root: true }
          )
          for (const subtreeElement of subtreeElements) {
            commit('DELETE_ITEM', {
              page: resolvedTargetPage,
              elementId: subtreeElement.id,
            })
            commit('ADD_ITEM', {
              page,
              element: { ...subtreeElement, page_id: page.id },
            })
            dispatch('_setElementNamespacePath', {
              page,
              element: getters.getElementById(page, subtreeElement.id),
            })
          }
          updateCachedValues(resolvedTargetPage)
        }
        throw error
      }
    }

    clearTimeout(updateContext.moveTimeout)
    updateContext.moveTimeout = setTimeout(fire, 1000)
  },
  /**
   * forceMove is a local-only move used by realtime events. It applies the
   * move directly to the page graph using the graph-based positioning triplet
   * (referenceElementId, position, placeInContainer) that the backend sends.
   */
  forceMove(
    { dispatch, getters },
    { page, elementId, referenceElementId, position, placeInContainer }
  ) {
    const element = getters.getElementById(page, elementId)
    if (!element) return

    const referenceElement = referenceElementId
      ? getters.getElementById(page, referenceElementId)
      : null

    dispatch('graphMove', {
      page,
      elementToMove: element,
      referenceElement,
      position: position ?? 'south',
      output: placeInContainer ?? '',
    })
  },
  async duplicate({ commit, dispatch }, { builder, page, elementId }) {
    const { $client } = this
    const {
      data: { elements, workflow_actions: workflowActions, graph },
    } = await ElementService($client).duplicate(elementId)

    // Apply the graph BEFORE calling forceCreate. forceCreate skips the
    // root-chain append when the element is already present in page.graph,
    // so pre-populating prevents duplicated elements from appearing at root
    // level in addition to their correct position inside a container slot.
    // The backend returns the full graph, so replace the local graph instead of
    // merging a patch into it.
    dispatch('page/forceUpdate', { page, values: { graph } }, { root: true })

    const elementPromises = elements.map((element) =>
      dispatch('forceCreate', { page, element })
    )
    const workflowActionPromises = workflowActions.map((workflowAction) =>
      dispatch(
        'builderWorkflowAction/forceCreate',
        { page, workflowAction },
        { root: true }
      )
    )

    await Promise.all(elementPromises.concat(workflowActionPromises))
    updateCachedValues(page)

    // elements[0] is always the root duplicate (children follow in order)
    commit('SELECT_ITEM', { builder, element: elements[0] })

    return elements
  },
  emitElementEvent({ getters }, { event, elements, ...rest }) {
    const { $registry } = this
    elements.forEach((element) => {
      const elementType = $registry.get('element', element.type)
      elementType.onElementEvent(event, { element, ...rest })
    })
  },
  _setElementNamespacePath({ commit, dispatch, getters }, { page, element }) {
    const { $registry } = this
    const elementType = $registry.get('element', element.type)
    const elementNamespacePath = elementType.getElementNamespacePath(
      element,
      page
    )
    commit('_SET_ELEMENT_NAMESPACE_PATH', {
      element,
      path: elementNamespacePath,
    })
  },
  refreshCachedValues(_, { page }) {
    updateCachedValues(page)
  },
}

const getters = {
  getElementById: (state, getters) => (page, id) => {
    if (id && Object.prototype.hasOwnProperty.call(page.elementMap, `${id}`)) {
      return page.elementMap[`${id}`]
    }
    return null
  },
  getElementByIdInPages: (state, getters) => (pages, id) => {
    for (const page of pages) {
      const found = getters.getElementById(page, id)
      if (found) {
        return found
      }
    }
    return null
  },
  getElementsOrdered: (state, getters) => (page) => {
    return page.orderedElements
  },
  getRootElements: (state, getters) => (page) => {
    const handler = new ElementGraphHandler(page)
    const result = []
    const visited = new Set()
    let currentId = page.graph?.['0']
    while (currentId && !visited.has(currentId)) {
      visited.add(currentId)
      const el = handler.getElement(currentId)
      if (el) result.push(el)
      currentId = handler.getInfo(currentId)?.next?.['']?.[0] ?? null
    }

    // Elements that exist on the page but are absent from the graph entirely (e.g.
    // records created during a not-yet-zero-downtime deployment) have no parent, so
    // surface them as root elements at the bottom rather than hiding them. A graphed
    // element — root or nested — always has its id as a key in the graph, so this
    // only picks up true orphans, never container children.
    const graph = page.graph || {}
    const elementMap = handler.getPointMap()
    for (const id of Object.keys(elementMap)) {
      if (!(id in graph)) {
        result.push(elementMap[id])
      }
    }

    return result
  },
  getChildren: (state, getters) => (page, element) => {
    if (!page.graph?.[element?.id]) return []
    return new ElementGraphHandler(page).getChildren(element)
  },
  getDescendants: (state, getters) => (page, element) => {
    const getAllDescendants = (page, element) => {
      const children = getters.getChildren(page, element)
      if (children.length === 0) {
        return []
      } else {
        return children.flatMap((child) => [
          child,
          ...getAllDescendants(page, child),
        ])
      }
    }
    return getAllDescendants(page, element)
  },
  getParent: (state, getters) => (page, element) => {
    if (!element?.id) return null
    // parentMap is always set by updateCachedValues in the running app;
    // the fallback only applies to tests that construct page objects manually.
    const parentMap =
      page.parentMap ??
      ElementGraphHandler.buildElementMaps(page?.graph ?? {}).parentMap
    const parentId = parentMap[element.id]
    return parentId ? getters.getElementById(page, parentId) : null
  },
  /**
   * Given an element, return all its ancestors until we reach the root element.
   */
  getAncestors:
    (state, getters) =>
    (
      page,
      element,
      { parentFirst = false, predicate = () => true, includeSelf = false } = {}
    ) => {
      const getElementAncestors = (element) => {
        const parentElement = getters.getParent(page, element)
        if (parentElement) {
          return [...getElementAncestors(parentElement), parentElement]
        } else {
          return []
        }
      }
      const ancestors = (
        includeSelf
          ? [...getElementAncestors(element), element]
          : getElementAncestors(element)
      ).filter(predicate)
      return parentFirst ? ancestors.reverse() : ancestors
    },
  getSiblings: (state, getters) => (page, element) => {
    const parent = getters.getParent(page, element)
    if (parent === null) {
      return getters.getRootElements(page)
    }
    try {
      const handler = new ElementGraphHandler(page)
      return handler.getChildrenInPlace(
        parent,
        element.place_in_container ?? ''
      )
    } catch {
      return []
    }
  },
  getElementPosition:
    (state, getters) =>
    (page, element, sameType = false) => {
      const elements = getters.getElementsOrdered(page)

      return (
        (sameType
          ? elements.filter(({ type }) => type === element.type)
          : elements
        ).findIndex(({ id }) => id === element.id) + 1
      )
    },
  getElementsInPlace:
    (state, getters) => (page, parentId, placeInContainer) => {
      if (parentId === null || parentId === undefined) {
        return getters.getRootElements(page)
      }
      const handler = new ElementGraphHandler(page)
      const parent = handler.getElement(parentId)
      if (!parent) return []
      return handler.getChildrenInPlace(parent, placeInContainer ?? '')
    },
  getPreviousElement: (state, getters) => (page, before) => {
    if (!before?.id) return null
    try {
      const positions = new ElementGraphHandler(page).getPreviousPositions(
        before
      )
      const southPosition = positions.findLast(([, pos]) => pos === 'south')
      return southPosition ? southPosition[0] : null
    } catch {
      return null
    }
  },
  getNextElement: (state, getters) => (page, after) => {
    if (!after?.id) return null
    const nextList = new ElementGraphHandler(page).getNextElements(after)
    return nextList[0] ?? null
  },
  getSelected: (state) => (builder) => {
    return builder.selectedElement
  },
  getElementNamespacePath: (state) => (element) => {
    return element._.elementNamespacePath
  },
  /**
   * Given an element, return its closest sibling element.
   */
  getClosestSiblingElement: (state, getters) => (page, element) => {
    if (!element) {
      return null
    }

    const siblings = getters.getSiblings(page, element)

    // Exclude the element itself from the list of siblings
    const otherSiblings = siblings.filter((el) => el.id !== element.id)

    if (otherSiblings.length) {
      const index = siblings.findIndex((el) => el.id === element.id)
      const nextIndex = Math.max(index - 1, 0)
      return otherSiblings[nextIndex]
    }

    const parent = getters.getParent(page, element)
    if (parent) {
      return parent
    }

    const rootElements = getters
      .getRootElements(page)
      .filter((el) => el.id !== element.id)
    if (rootElements.length) {
      return rootElements[0]
    }

    return null
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
