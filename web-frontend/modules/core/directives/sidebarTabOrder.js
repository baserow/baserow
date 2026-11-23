const controls =
  'a[href], button, input, select, textarea, summary, iframe, [contenteditable]:not([contenteditable="false"]), [tabindex]'

const observers = new WeakMap()

function removeTabStop(element) {
  if (
    element.matches(controls) &&
    !element.hasAttribute('data-sidebar-tab-stop') &&
    element.getAttribute('tabindex') !== '-1'
  ) {
    element.setAttribute('tabindex', '-1')
  }
}

function removeTabStopsIn(element) {
  removeTabStop(element)
  element.querySelectorAll(controls).forEach(removeTabStop)
}

export default {
  mounted(element) {
    removeTabStopsIn(element)
    // Application children and plugin entries can be mounted independently.
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'attributes') {
          removeTabStop(mutation.target)
        } else {
          for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              removeTabStopsIn(node)
            }
          }
        }
      }
    })
    observer.observe(element, {
      attributes: true,
      attributeFilter: ['href', 'tabindex', 'contenteditable'],
      childList: true,
      subtree: true,
    })
    observers.set(element, observer)
  },
  beforeUnmount(element) {
    observers.get(element)?.disconnect()
    observers.delete(element)
  },
}
