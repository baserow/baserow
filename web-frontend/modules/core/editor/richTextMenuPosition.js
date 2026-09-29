import { posToDOMRect } from '@tiptap/core'

export const isRichTextSelectionVisible = (editor, scrollTargets) => {
  if (!editor || !scrollTargets) {
    return true
  }

  const { from, to } = editor.state.selection
  const selectionRect = posToDOMRect(editor.view, from, to)
  const targets = Array.isArray(scrollTargets) ? scrollTargets : [scrollTargets]

  return targets.every((target) => {
    const containerRect =
      target === window
        ? { top: 0, bottom: window.innerHeight }
        : target.getBoundingClientRect()
    return (
      selectionRect.bottom > containerRect.top &&
      selectionRect.top < containerRect.bottom
    )
  })
}
