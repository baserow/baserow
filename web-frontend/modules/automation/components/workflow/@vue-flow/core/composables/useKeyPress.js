import { ref, unref, watch } from 'vue'
import { onKeyStroke, useEventListener } from '@vueuse/core'

const inputTags = ['INPUT', 'SELECT', 'TEXTAREA']

export function isInputDOMNode(event) {
  const target = event.composedPath?.()?.[0] || event.target

  const hasAttribute =
    typeof target?.hasAttribute === 'function'
      ? target.hasAttribute('contenteditable')
      : false

  const closest =
    typeof target?.closest === 'function' ? target.closest('.nokey') : null

  // when an input field is focused we don't want to trigger deletion or movement of nodes
  return inputTags.includes(target?.nodeName) || hasAttribute || !!closest
}

// we want to be able to do a multi selection event if we are in an input field
function wasModifierPressed(event) {
  return event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
}

function isKeyMatch(pressedKey, keyToMatch, pressedKeys, isKeyUp) {
  const keyCombination = keyToMatch
    .replace('+', '\n')
    .replace('\n\n', '\n+')
    .split('\n')
    .map((k) => k.trim().toLowerCase())

  if (keyCombination.length === 1) {
    return pressedKey.toLowerCase() === keyToMatch.toLowerCase()
  }

  // we need to remove the key *after* checking for a match otherwise a combination like 'shift+a' would never get unmatched/reset
  if (!isKeyUp) {
    pressedKeys.add(pressedKey.toLowerCase())
  }

  const isMatch = keyCombination.every(
    (key, index) =>
      pressedKeys.has(key) &&
      Array.from(pressedKeys.values())[index] === keyCombination[index]
  )

  if (isKeyUp) {
    pressedKeys.delete(pressedKey.toLowerCase())
  }

  return isMatch
}

function createKeyPredicate(keyFilter, pressedKeys) {
  return (event) => {
    if (!event.code && !event.key) {
      return false
    }

    const keyOrCode = useKeyOrCode(event.code, keyFilter)

    // if the keyFilter is an array of multiple keys, we need to check each possible key combination
    if (Array.isArray(keyFilter)) {
      return keyFilter.some((key) =>
        isKeyMatch(event[keyOrCode], key, pressedKeys, event.type === 'keyup')
      )
    }

    // if the keyFilter is a string, we need to check if the key matches the string
    return isKeyMatch(
      event[keyOrCode],
      keyFilter,
      pressedKeys,
      event.type === 'keyup'
    )
  }
}

function useKeyOrCode(code, keysToWatch) {
  return Array.isArray(keysToWatch)
    ? keysToWatch.includes(code)
      ? 'code'
      : 'key'
    : keysToWatch === code
    ? 'code'
    : 'key'
}

/**
 * Composable that returns a boolean value if a key is pressed
 *
 * @public
 * @param keyFilter - Can be a boolean, a string, an array of strings or a function that returns a boolean. If it's a boolean, it will act as if the key is always pressed. If it's a string, it will return true if a key matching that string is pressed. If it's an array of strings, it will return true if any of the strings match a key being pressed, or a combination (e.g. ['ctrl+a', 'ctrl+b'])
 * @param options - Options object
 */
export function useKeyPress(keyFilter, options = {}) {
  const actInsideInputWithModifier = ref(
    options?.actInsideInputWithModifier ?? false
  )
  const target = ref(options?.target ?? window)
  const preventDefault = ref(options?.preventDefault ?? true)

  const isPressed = ref(unref(keyFilter) === true)

  let modifierPressed = false

  const pressedKeys = new Set()

  let currentFilter = createKeyFilterFn(unref(keyFilter))

  watch(
    () => unref(keyFilter),
    (nextKeyFilter, previousKeyFilter) => {
      // if the previous keyFilter was a boolean but is now something else, we need to reset the isPressed value
      if (
        typeof previousKeyFilter === 'boolean' &&
        typeof nextKeyFilter !== 'boolean'
      ) {
        reset()
      }

      currentFilter = createKeyFilterFn(nextKeyFilter)
    },
    {
      immediate: true,
    }
  )

  useEventListener(['blur', 'contextmenu'], reset)

  onKeyStroke(
    (...args) => currentFilter(...args),
    (e) => {
      modifierPressed = wasModifierPressed(e)

      const preventAction =
        (!modifierPressed ||
          (modifierPressed && !actInsideInputWithModifier.value)) &&
        isInputDOMNode(e)

      if (preventAction) {
        return
      }

      const target = e.composedPath?.()?.[0] || e.target
      const isInteractiveElement =
        target?.nodeName === 'BUTTON' || target?.nodeName === 'A'

      if (!preventDefault.value && (modifierPressed || !isInteractiveElement)) {
        e.preventDefault()
      }

      isPressed.value = true
    },
    { eventName: 'keydown', target }
  )

  onKeyStroke(
    (...args) => currentFilter(...args),
    (e) => {
      if (isPressed.value) {
        const preventAction =
          (!modifierPressed ||
            (modifierPressed && !actInsideInputWithModifier.value)) &&
          isInputDOMNode(e)

        if (preventAction) {
          return
        }

        modifierPressed = false
        isPressed.value = false
      }
    },
    { eventName: 'keyup', target }
  )

  function reset() {
    modifierPressed = false

    pressedKeys.clear()

    isPressed.value = unref(keyFilter) === true
  }

  function createKeyFilterFn(keyFilter) {
    // if the keyFilter is null, we just set the isPressed value to false
    if (keyFilter === null) {
      reset()
      return () => false
    }

    // if the keyFilter is a boolean, we just set the isPressed value to that boolean
    if (typeof keyFilter === 'boolean') {
      reset()
      isPressed.value = keyFilter

      return () => false
    }

    if (Array.isArray(keyFilter) || typeof keyFilter === 'string') {
      return createKeyPredicate(keyFilter, pressedKeys)
    }

    return keyFilter
  }

  return isPressed
}
