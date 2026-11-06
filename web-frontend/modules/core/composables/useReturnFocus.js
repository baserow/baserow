/**
 * Gives the focus back to the element that had it when a modal opened, if it's
 * still on the page, once the modal is hidden.
 */
export function useReturnFocus() {
  let opener = null
  return {
    remember() {
      opener = document.activeElement
    },
    restore() {
      if (opener?.isConnected) {
        opener.focus()
      }
      opener = null
    },
  }
}
