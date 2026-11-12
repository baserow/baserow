const PENDING = Symbol('preHydrationInput')
const USE_EVENTS = ['input', 'change']
const USED_BEFORE_HYDRATION = '__baserowUsedBeforeHydration'

/**
 * Inline script for the document head. It records the inputs the user uses before
 * the page is hydrated, and once the HTML is parsed, resets the other inputs to their
 * server value. Firefox restores the previous values on reload, which would
 * otherwise be shown until the hydration.
 */
export const usedBeforeHydrationScript = `(function () {
  var used = (window.${USED_BEFORE_HYDRATION} = new WeakSet());
  ${JSON.stringify(USE_EVENTS)}.forEach(function (name) {
    document.addEventListener(name, function (event) {
      used.add(event.target);
    }, true);
  });
  document.addEventListener('readystatechange', function () {
    if (document.readyState !== 'interactive') {
      return;
    }
    document.querySelectorAll('input, textarea').forEach(function (el) {
      if (used.has(el)) {
        return;
      }
      if (el.checked !== el.defaultChecked) {
        el.checked = el.defaultChecked;
      }
      if (el.value !== el.defaultValue) {
        el.value = el.defaultValue;
      }
    });
  });
})();`

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
 * user sees. A value the browser restored on reload (Firefox does) is reset instead.
 */
export default {
  created(el) {
    // Only an element being hydrated is already in the document at this point.
    if (!el.parentNode) {
      return
    }
    const pending = { used: false, value: null }
    const checkable = isCheckable(el)
    const changed = checkable
      ? el.checked !== el.defaultChecked
      : el.value !== el.defaultValue
    if (changed && window[USED_BEFORE_HYDRATION]?.has(el)) {
      pending.value = checkable ? el.checked : el.value
    } else if (changed && checkable) {
      el.checked = el.defaultChecked
    } else if (changed) {
      el.value = el.defaultValue
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
