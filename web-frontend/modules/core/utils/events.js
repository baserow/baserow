/*
  This function is a helper which determines whether the pressed key
  is 'not a Control Key Character'
  thereby determining if the key is a 'printable character'.
  Any key combination with a control or a meta key is NOT a
  'printable character' thereby making it possible to use combinations
  such as CTRL+C/CTRL+V.
*/
export function isPrintableUnicodeCharacterKeyPress(event) {
  if (event == null || isOsSpecificModifierPressed(event)) {
    return false
  }
  const { key } = event

  const nonControlCharacterRegex = /^\P{C}$/iu
  if (nonControlCharacterRegex.test(key)) {
    return true
  }
  return false
}

/**
 * Detects if the user is on a Mac platform
 * @returns {boolean} True if the user is on Mac, false otherwise
 */
export const isMac = () => {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false
  }
  const platform = navigator.platform || ''
  return platform.toUpperCase().includes('MAC')
}

/**
 * This function is a helper which determines whether the pressed key
 * is the CMD key on Mac or the CTRL key on Windows/Linux.
 */
export const isOsSpecificModifierPressed = (event) => {
  return isMac() ? event.metaKey : event.ctrlKey
}

export const keyboardShortcutsToPriorityEventBus = (event, priorityBus) => {
  if (
    isOsSpecificModifierPressed(event) &&
    event.shiftKey &&
    event.key.toLowerCase() === 's'
  ) {
    priorityBus.$emit('start-search', { event })
  }
}
