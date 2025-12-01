import BigNumber from 'bignumber.js'

import ElementService from '@baserow/modules/builder/services/element'
import PublicBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import { calculateTempOrder } from '@baserow/modules/core/utils/order'
import { uuid } from '@baserow/modules/core/utils/string'

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

/**
 * As the store data come first from the SSR generated version, we don't have the
 * BigNumber anymore so we need to make sure we use BigNumber when we compare things.
 * @param {Object} element
 * @returns a BigNumber object or null if the element or the order is missing.
 */
const getOrder = (element) => {
  return element?.order ? new BigNumber(element.order) : null
}

/** Recursively order the elements from up to down and left to right */
const orderElements = (elements, parentElementId = null) => {
  return elements
    .filter(
      ({ parent_element_id: curentParentElementId }) =>
        curentParentElementId === parentElementId
    )
    .sort((a, b) => {
      if (a.place_in_container !== b.place_in_container) {
        return a.place_in_container > b.place_in_container ? 1 : -1
      }

      return getOrder(a).gt(getOrder(b)) ? 1 : -1
    })
    .map((element) => [element, ...orderElements(elements, element.id)])
    .flat()
}

const updateCachedValues = (page) => {
  page.orderedElements = orderElements(page.elements)
  page.elementMap = Object.fromEntries(
    page.elements.map((element) => [`${element.id}`, element])
  )
}

const mutations = {
  SET_ITEMS(state, { builder, page, elements }) {
    builder.selectedElement = null
    page.elements = elements.map((element) =>
      populateElement(element, this.$registry)
    )
    updateCachedValues(page)
  },
  ADD_ITEM(state, { page, element, beforeId = null }) {
    page.elements.push(populateElement(element, this.$registry))
    updateCachedValues(page)
  },
  UPDATE_ITEM(state, { builder, page, element: elementToUpdate, values }) {
    let updateCached = false
    page.elements.forEach((element) => {
      if (element.id === elementToUpdate.id) {
        if (
          (values.order !== undefined && values.order !== element.order) ||
          (values.place_in_container !== undefined &&
            values.place_in_container !== element.place_in_container)
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
      // We need to update cached values only if order or place of an element has
      // changed or if an element has been added or removed.
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
  MOVE_ITEM(state, { page, index, oldIndex }) {
    page.elements.splice(index, 0, page.elements.splice(oldIndex, 1)[0])
  },
  SELECT_ITEM(state, { builder, element }) {
    builder.selectedElement = element
  },
  CLEAR_ITEMS(state, { page }) {
    page.elements = []
    updateCachedValues(page)
  },
  _SET_ELEMENT_NAMESPACE_PATH(state, { element, path }) {
    element._.elementNamespacePath = path
  },
  SET_REPEAT_ELEMENT_COLLAPSED(state, { element, collapsed }) {
    element._.collapsed = collapsed
  },
}

const actions = {
  clearAll({ commit }, { page }) {
    commit('CLEAR_ITEMS', { page })
  },
  forceCreate({ dispatch, commit }, { page, element }) {
    commit('ADD_ITEM', { page, element })
    dispatch('_setElementNamespacePath', { page, element })

    const elementType = this.$registry.get('element', element.type)
    elementType.afterCreate(element, page)
  },
  forceUpdate({ commit }, { builder, page, element, values }) {
    commit('UPDATE_ITEM', { builder, page, element, values })
    const elementType = this.$registry.get('element', element.type)
    elementType.afterUpdate(element, page)
  },
  forceDelete({ commit, getters }, { builder, page, elementId }) {
    const elementToDelete = getters.getElementById(page, elementId)

    if (getters.getSelected(builder)?.id === elementId) {
      commit('SELECT_ITEM', { builder, element: null })
    }
    commit('DELETE_ITEM', { page, elementId })

    const elementType = this.$registry.get('element', elementToDelete.type)
    elementType.afterDelete(elementToDelete, page)
  },
  forceMove(
    { commit, getters },
    {
      builder,
      page,
      elementId,
      beforeElementId,
      parentElementId,
      placeInContainer,
    }
  ) {
    const element = getters.getElementById(page, elementId)

    let tempOrder = ''
    // Compute temporary order while waiting for the update from the server
    if (beforeElementId) {
      // If we have a before element then we should place the element
      // between the before element and the element before the before element.
      const beforeElement = getters.getElementById(page, beforeElementId)
      const beforeBeforeElement = getters.getPreviousElement(
        page,
        beforeElement
      )
      const afterOrder = getOrder(beforeElement)
      const beforeOrder = getOrder(beforeBeforeElement)
      tempOrder = calculateTempOrder(beforeOrder, afterOrder)
    } else {
      // Otherwise it's should be placed as the last in the column so we get the last
      // element and we just add one.
      const lastElement = getters
        .getElementsInPlace(page, parentElementId, placeInContainer)
        .at(-1)
      tempOrder = calculateTempOrder(getOrder(lastElement), null)
    }

    commit('UPDATE_ITEM', {
      builder,
      page,
      element,
      values: {
        order: tempOrder,
        parent_element_id: parentElementId,
        place_in_container: placeInContainer,
      },
    })
  },
  select({ commit }, { builder, element }) {
    updateContext.lastUpdatedValues = null
    commit('SELECT_ITEM', { builder, element })
  },
  async create(
    { dispatch },
    {
      builder,
      page,
      elementType: elementTypeName,
      beforeId = null,
      values = null,
      forceCreate = true,
    }
  ) {
    const elementType = this.$registry.get('element', elementTypeName)
    const updatedValues = elementType.getDefaultValues(page, values)
    const { data: element } = await ElementService(this.$client).create(
      page.id,
      elementTypeName,
      beforeId,
      updatedValues
    )

    if (forceCreate) {
      await dispatch('forceCreate', { page, element })

      await dispatch('select', { builder, element })
    }

    return element
  },
  async update({ dispatch }, { builder, page, element, values }) {
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
      await ElementService(this.$client).update(element.id, values)
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
    const oldValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(element, name)) {
        oldValues[name] = element[name]
        // Accumulate the changed values to send all the ongoing changes with the
        // final request
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
          await ElementService(this.$client).update(element.id, toUpdate)
          updateContext.lastUpdatedValues = null
          resolve()
        } catch (error) {
          // Revert to old values on error
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
  async delete({ dispatch, getters }, { builder, page, elementId }) {
    const elementToDelete = getters.getElementById(page, elementId)
    const descendants = getters.getDescendants(page, elementToDelete)

    // First delete all children
    await Promise.all(
      descendants.map((descendant) =>
        dispatch('forceDelete', { builder, page, elementId: descendant.id })
      )
    )

    await dispatch('forceDelete', { builder, page, elementId })

    try {
      await ElementService(this.$client).delete(elementId)
    } catch (error) {
      await dispatch('forceCreate', {
        page,
        element: elementToDelete,
      })
      // Then restore all children
      await Promise.all(
        descendants.map((descendant) =>
          dispatch('forceCreate', { page, element: descendant })
        )
      )
      throw error
    }
  },
  async fetch({ dispatch, commit }, { builder, page }) {
    const { data: elements } = await ElementService(this.$client).fetchAll(
      page.id
    )

    commit('SET_ITEMS', { builder, page, elements })

    // Set the element namespace path of all elements we've fetched.
    await Promise.all(
      elements.map((element) =>
        dispatch('_setElementNamespacePath', { page, element })
      )
    )

    return elements
  },
  async fetchPublished({ dispatch, commit }, { builder, page }) {
    const { data: elements } = await PublicBuilderService(
      this.$client
    ).fetchElements(page)

    commit('SET_ITEMS', { builder, page, elements })

    // Set the element namespace ath of all published elements we've fetched.
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
      beforeElementId,
      parentElementId = null,
      placeInContainer = null,
    }
  ) {
    const element = getters.getElementById(page, elementId)
    const { order: previousOrder, place_in_container: previousPlace } = element

    await dispatch('forceMove', {
      builder,
      page,
      elementId,
      beforeElementId,
      parentElementId,
      placeInContainer,
    })

    const fire = async () => {
      try {
        const { data: elementUpdated } = await ElementService(
          this.$client
        ).move(elementId, beforeElementId, parentElementId, placeInContainer)

        dispatch('forceUpdate', {
          builder,
          page,
          element: elementUpdated,
          values: {
            order: elementUpdated.order,
            place_in_container: elementUpdated.place_in_container,
            parent_element_id: elementUpdated.parent_element_id,
          },
        })
      } catch (error) {
        // Restore previous order and place_in_container properties
        await dispatch('forceUpdate', {
          builder,
          page,
          element,
          values: { order: previousOrder, place_in_container: previousPlace },
        })
        throw error
      }
    }

    clearTimeout(updateContext.moveTimeout)
    updateContext.moveTimeout = setTimeout(fire, 1000)
  },
  async duplicate({ commit, dispatch, getters }, { builder, page, elementId }) {
    const {
      data: { elements, workflow_actions: workflowActions },
    } = await ElementService(this.$client).duplicate(elementId)

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

    const elementToDuplicate = getters.getElementById(page, elementId)
    const elementToSelect = elements.find(
      ({ parent_element_id: parentId }) =>
        parentId === elementToDuplicate.parent_element_id
    )

    commit('SELECT_ITEM', { builder, element: elementToSelect })

    return elements
  },
  emitElementEvent({ getters }, { event, elements, ...rest }) {
    elements.forEach((element) => {
      const elementType = this.$registry.get('element', element.type)
      elementType.onElementEvent(event, { element, ...rest })
    })
  },
  _setElementNamespacePath({ commit, dispatch, getters }, { page, element }) {
    const elementType = this.$registry.get('element', element.type)
    const elementNamespacePath = elementType.getElementNamespacePath(
      element,
      page
    )
    commit('_SET_ELEMENT_NAMESPACE_PATH', {
      element,
      path: elementNamespacePath,
    })
  },
  setRepeatElementCollapsed({ commit }, { element, collapsed }) {
    commit('SET_REPEAT_ELEMENT_COLLAPSED', {
      element,
      collapsed,
    })
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
    return getters
      .getElementsOrdered(page)
      .filter((e) => e.parent_element_id === null)
  },
  getChildren: (state, getters) => (page, element) => {
    return getters
      .getElementsOrdered(page)
      .filter((e) => e.parent_element_id === element.id)
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
    return getters.getElementById(page, element?.parent_element_id)
  },
  /**
   * Given an element, return all its ancestors until we reach the root element.
   * If `parentFirst` is `true` then we reverse the array of elements so that
   * the element's immediate parent is first, otherwise the root element will be first.
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
    return getters
      .getElementsOrdered(page)
      .filter((e) => e.parent_element_id === element.parent_element_id)
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
      return getters
        .getElementsOrdered(page)
        .filter(
          (e) =>
            e.parent_element_id === parentId &&
            e.place_in_container === placeInContainer
        )
    },
  getPreviousElement: (state, getters) => (page, before) => {
    const elementsInPlace = getters.getElementsInPlace(
      page,
      before.parent_element_id,
      before.place_in_container
    )
    return before
      ? elementsInPlace
          .reverse()
          .find((e) => getOrder(e).lt(getOrder(before))) || null
      : elementsInPlace.at(-1)
  },
  getNextElement: (state, getters) => (page, after) => {
    const elementsInPlace = getters.getElementsInPlace(
      page,
      after.parent_element_id,
      after.place_in_container
    )

    return elementsInPlace.find((e) => getOrder(e).gt(getOrder(after)))
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

    // If the element has siblings, return the closest previous sibling.
    // Default to the first (zeroth) sibling.
    if (otherSiblings.length) {
      const index = siblings.findIndex((el) => el.id === element.id)
      const nextIndex = Math.max(index - 1, 0)
      return otherSiblings[nextIndex]
    }

    // Return the container element if the element has a parent
    if (element.parent_element_id) {
      return getters.getElementById(page, element.parent_element_id)
    }

    // Find root element
    const rootElements = getters
      .getRootElements(page)
      .filter((el) => el.id !== element.id)
    if (rootElements.length) {
      return rootElements[0]
    }

    return null
  },
  getRepeatElementCollapsed: (state) => (element) => {
    return element._.collapsed
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
