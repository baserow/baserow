import { defineAsyncComponent } from 'vue'

export const loadRichTextEditor = () =>
  import('@baserow/modules/core/components/editor/RichTextEditor.vue')

// Callers invoking editor methods right after mount must await loadRichTextEditor().
export const RichTextEditor = defineAsyncComponent(loadRichTextEditor)
