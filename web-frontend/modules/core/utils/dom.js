import { Comment, Fragment } from 'vue'

/**
 * Checks if the target is the same as the provided element of that the element
 * contains the target. Returns true is this is the case.
 *
 * @returns boolean
 */
export const isElement = (element, target) => {
  return element != null && (element === target || element.contains(target))
}

/**
 * Checks if the provided object is an html dom element.
 *
 * @returns boolean
 */
export const isDomElement = (obj) => {
  try {
    return obj instanceof HTMLElement
  } catch (e) {
    return (
      typeof obj === 'object' &&
      obj.nodeType === 1 &&
      typeof obj.style === 'object' &&
      typeof obj.ownerDocument === 'object'
    )
  }
}

/**
 * This function will focus a contenteditable and place the cursor at the end.
 *
 * @param element
 */
export const focusEnd = (element) => {
  const range = document.createRange()
  const selection = window.getSelection()
  range.selectNodeContents(element)
  range.collapse(false)
  selection.removeAllRanges()
  selection.addRange(range)
  element.focus()
}

/**
 * Get the closest parent element that matches a predicate function.
 *
 * @param {Element} element - The starting element.
 * @param {Function} predicate - A function that takes an element and returns a boolean.
 * @returns {Element|null} The matching parent element or null if no match is found.
 */
export const getParentMatchingPredicate = (element, predicate) => {
  while (element !== null && element.nodeType === Node.ELEMENT_NODE) {
    if (predicate(element)) {
      return element
    }
    element = element.parentElement
  }
  return null
}

/**
 * Finds the closest scrollable parent element of the provided element.
 */
export const findScrollableParent = (element) => {
  return getParentMatchingPredicate(
    element,
    (element) =>
      element.scrollHeight > element.clientHeight ||
      element.scrollWidth > element.clientWidth
  )
}

/**
 * @typedef {Object} OnClickOutsideOptions
 * @property {Array<HTMLElement|null|undefined>|(() => Array<HTMLElement|null|undefined>)} [ignoreElements]
 *   Extra elements (e.g. opener button, teleported child menus) that count as “inside” for
 *   closing. Pass a function to resolve element on each event so late-mounted nodes work.
 *   Mousedown is snapshotted when the target is not under `el` so optimistic unmounts
 *   before `click` still count as inside.
 */

/**
 * Resolves ignoreElements option to a list of DOM elements.
 *
 * @param {OnClickOutsideOptions|undefined} options
 * @returns {HTMLElement[]}
 */
const resolveIgnoreElements = (options) => {
  if (!options || !options.ignoreElements) {
    return []
  }
  const raw =
    typeof options.ignoreElements === 'function'
      ? options.ignoreElements()
      : options.ignoreElements
  const list = Array.isArray(raw) ? raw : []
  return list.filter((node) => node != null)
}

/**
 * @param {HTMLElement[]} elements
 * @param {EventTarget|null} target
 * @returns {boolean}
 */
const isTargetInsideAnyElement = (elements, target) => {
  return elements.some((element) => isElement(element, target))
}

/**
 * Detects clicks outside el element and call callback
 *
 * Returns a callback to unregister click handlers after successful outside click
 * @param {HTMLElement} el
 * @param {(target: EventTarget, event: MouseEvent) => void} callback
 * @param {OnClickOutsideOptions} [options]
 * @returns {() => void}
 */
export const onClickOutside = (el, callback, options) => {
  const insideEvent = new Set()

  // Firefox and Chrome both can both have a different `target` element on `click`
  // when you release the mouse at different coordinates. Therefore we expect this
  // variable to be set on mousedown to be consistent.
  let downElement = null

  /** True if mousedown started inside an ignore element (while not under `el`); see snapshot comment below. */
  let mousedownInsideIgnored = false

  // Add the event to the `insideEvent` map. This allow to be sure a click event has
  // been triggered from an element inside this context, even if the element has
  // been removed after in the meantime.
  const clickOutsideClickEvent = (event) => {
    insideEvent.add(event)
  }
  el.addEventListener('click', clickOutsideClickEvent)

  const clickOutsideMouseDownEvent = (event) => {
    downElement = event.target
    const elements = resolveIgnoreElements(options)
    // Only snapshot when not on `el`; clicks on `el` are handled via insideEvent.
    // When ignore elements are teleported outside `el`, we must record mousedown here so
    // optimistic updates that unmount before `click` still count as inside.
    if (!isElement(el, event.target) && elements.length > 0) {
      mousedownInsideIgnored = isTargetInsideAnyElement(elements, event.target)
    } else {
      mousedownInsideIgnored = false
    }
  }
  document.body.addEventListener('mousedown', clickOutsideMouseDownEvent)

  const clickOutsideEvent = (event) => {
    const target = downElement || event.target

    // If the event is from current context or any element inside current context
    // the current event should be in the insideEvent map, even if the element
    // has been removed from the DOM in the meantime
    const insideContext = insideEvent.has(event)
    if (insideContext) {
      insideEvent.delete(event)
    }

    const elements = resolveIgnoreElements(options)
    const insideIgnoredElement =
      mousedownInsideIgnored ||
      (elements.length > 0 &&
        isTargetInsideAnyElement(elements, downElement || event.target))
    mousedownInsideIgnored = false

    // If the click was outside the context element because we want to ignore
    // clicks inside it or any child of this element
    if (!isElement(el, target) && !insideContext && !insideIgnoredElement) {
      callback(target, event)
    }
  }
  document.body.addEventListener('click', clickOutsideEvent)

  return () => {
    el.removeEventListener('click', clickOutsideClickEvent)
    document.body.removeEventListener('mousedown', clickOutsideMouseDownEvent)
    document.body.removeEventListener('click', clickOutsideEvent)
  }
}

/**
 * Return whether one of the ancestors of the given node matches the given predicate.
 *
 * @param {DomElement} node The node to start the search for.
 * @param {function} predicate The predicate to test on every ancestor.
 * @param {DomElement} stop If provided, the search will stop when this element is met.
 *   It should an ancestor of the given node.
 * @returns Whether one of the ancestors matches the predicate.
 */
export const doesAncestorMatchPredicate = (node, predicate, stop) => {
  while (node != null) {
    if (stop === node) {
      return false
    }
    if (predicate(node)) {
      return true
    }
    node = node.parentNode
  }
  return false
}

/**
 * Checks a given predicate on all intermediate DOM elements between a descendant and its ancestor.
 *
 * @param {HTMLElement} ancestor - The ancestor DOM element.
 * @param {HTMLElement} descendant - The descendant DOM element. The function assumes that
 *                                   this is a descendant of the ancestor element.
 * @param {Function} predicate - A function that takes a DOM element as an argument and returns
 *                               a boolean. This function is called on each intermediate element
 *                               between the descendant and the ancestor.
 * @returns {boolean} - Returns true if the predicate returns true for at least one intermediate
 *                      element between the descendant and ancestor. Otherwise, returns false.
 *
 * @example
 * // Example usage
 * const ancestorElement = document.getElementById('parent');
 * const descendantElement = document.getElementById('child');
 * const result = checkIntermediateElements(ancestorElement, descendantElement, (el) => {
 *   return el.tagName === 'DIV';
 * });
 * console.log(result); // Outputs true if any intermediate element is a <div>, otherwise false.
 */
export const checkIntermediateElements = (ancestor, descendant, predicate) => {
  for (let el = descendant; el && el !== ancestor; el = el.parentElement) {
    if (predicate(el)) {
      return true
    }
  }
  return false
}

/**
 * Calculates the outer most bounding rect of multiple elements provided. This can be
 * used to show a specific area, highlighting multiple elements.
 */
export const getCombinedBoundingClientRect = (elements) => {
  if (!elements.length) return null

  const rects = elements.map((el) => el.getBoundingClientRect())

  const top = Math.min(...rects.map((r) => r.top))
  const left = Math.min(...rects.map((r) => r.left))
  const bottom = Math.max(...rects.map((r) => r.bottom))
  const right = Math.max(...rects.map((r) => r.right))

  return {
    top,
    left,
    bottom,
    right,
    width: right - left,
    height: bottom - top,
  }
}

/**
 * Checks if the provided argument contains real nodes and not just comments. This is
 * typically used to detect if a slot is not empty.
 */
export const hasRealNodes = (nodes) => {
  if (!nodes) return false
  if (!Array.isArray(nodes)) nodes = [nodes]

  return nodes.some((node) => {
    if (!node) return false

    // Ignore pure comments
    if (node.type === Comment) return false

    // For fragments, look into children
    if (node.type === Fragment) {
      return hasRealNodes(node.children)
    }

    // Anything else (element, text, component) counts as real content
    return true
  })
}

/**
 * A ref does not always return the dom element object. This helper method makes sure
 * that it's returned.
 */
export const getElementFromRef = (ref) => {
  const target = Array.isArray(ref) ? ref[0] : ref

  // element ref
  if (target instanceof Element) return target

  // component ref -> root DOM element
  if (target?.$el instanceof Element) return target.$el
}

/**
 * Teleported overlay root resolved from `$refs[key]` (via `getElementFromRef`),
 * or null if not an HTMLElement.
 */
export const getTeleportedElementFromRef = (refs, refKey) => {
  if (!refs || !refKey) {
    return null
  }
  const el = getElementFromRef(refs[refKey])
  return el instanceof HTMLElement ? el : null
}

// Wrapper for `modalEl` (Modal / baseModal teleported DOM root).
export const getModalTeleportedElement = (refs) =>
  getTeleportedElementFromRef(refs, 'modalEl')

// All teleported overlay roots under `component` (and `children`) to treat as inside for outside-click handling.
export const collectTeleportRootsForOutsideClick = (component) => {
  const elements = []
  if (!component) {
    return elements
  }
  if (typeof component.getTeleportedElement === 'function') {
    const el = component.getTeleportedElement()
    if (el instanceof HTMLElement) {
      elements.push(el)
    }
  }

  // Resolve the component that owns `children`.
  // Wrapper components (modal/context mixins) delegate to an inner Modal/Context
  // via getRootModal()/getRootContext(). The real `children` array lives on that
  // inner component, not on the wrapper itself.
  let inner = component
  if (typeof component.getRootModal === 'function') {
    inner = component.getRootModal() ?? component
  } else if (typeof component.getRootContext === 'function') {
    inner = component.getRootContext() ?? component
  }
  for (const nested of inner.children || []) {
    elements.push(...collectTeleportRootsForOutsideClick(nested))
  }
  return elements
}

/**
 * Returns true if `event.target` is inside any teleported root of the given
 * component ref (including nested children).
 */
export const isInsideTeleportedElement = (componentRef, event) => {
  if (!componentRef) return false
  const roots = collectTeleportRootsForOutsideClick(componentRef)
  return roots.some((el) => isElement(el, event.target))
}
