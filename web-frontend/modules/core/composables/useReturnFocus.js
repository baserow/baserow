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
