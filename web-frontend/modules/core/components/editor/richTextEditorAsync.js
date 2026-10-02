import { defineAsyncComponent } from 'vue'

export const loadRichTextEditor = () =>
  import('@baserow/modules/core/components/editor/RichTextEditor.vue')

// Preloading the module does not mount an editor. Ref methods must wait for its
// mounted hook and the next render tick.
export const RichTextEditor = defineAsyncComponent(loadRichTextEditor)
