const PENDING = Symbol('preHydrationInput')
const USE_EVENTS = ['input', 'change']

const isCheckable = (el) => el.type === 'checkbox'

/**
 * Replays a value typed before hydration by dispatching `input`, wrapped in `focus`
 * and `blur` if the user already left the input. Only dispatches `focus` if the
 * input has the focus without a typed value.
 */
const replayText = (el, typedValue) => {
  const focused = document.activeElement === el
  if (!focused && typedValue === null) {
    return
  }

  el.dispatchEvent(new FocusEvent('focus'))
  if (typedValue !== null) {
    el.value = typedValue
    el.dispatchEvent(new Event('input', { bubbles: true }))
    if (!focused) {
      el.dispatchEvent(new FocusEvent('blur'))
    }
  }
}

/**
 * Replays a checkbox toggled before hydration by dispatching `change`.
 */
const replayCheck = (el, checked) => {
  if (checked === null) {
    return
  }
  el.checked = checked
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

/**
 * A server-side rendered input can be used before the page is hydrated, but no
 * listener is attached yet. When Vue hydrates it, the value the user typed is
 * replaced by the state value, and the component never sees the events. This
 * directive records what the user did before hydration and replays the matching
 * events once the element is hydrated, so the component state matches what the
 * user sees.
 */
export default {
  created(el) {
    // Only an element being hydrated is already in the document at this point.
    if (!el.parentNode) {
      return
    }
    const pending = { used: false }
    if (isCheckable(el)) {
      pending.value = el.checked !== el.defaultChecked ? el.checked : null
    } else {
      pending.value = el.value !== el.defaultValue ? el.value : null
    }
    // The listeners are attached before `mounted`, which can be delayed by an async
    // sibling. If the user uses the hydrated input meanwhile, the component already
    // has the newer value, so nothing must be replayed.
    pending.onUse = () => (pending.used = true)
    USE_EVENTS.forEach((name) => el.addEventListener(name, pending.onUse))
    el[PENDING] = pending
  },
  mounted(el) {
    const pending = el[PENDING]
    if (!pending) {
      return
    }
    delete el[PENDING]
    USE_EVENTS.forEach((name) => el.removeEventListener(name, pending.onUse))
    if (pending.used) {
      return
    }

    if (isCheckable(el)) {
      replayCheck(el, pending.value)
    } else {
      replayText(el, pending.value)
    }
  },
}
