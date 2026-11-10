import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

// Share both component identity and a single feature import across containers.
export const ElementPreview = lazyComponent(() =>
  import('@baserow/modules/builder/components/editorRenderingBundle').then(
    (bundle) => bundle.ElementPreview
  )
)
export const AddElementZone = lazyComponent(() =>
  import('@baserow/modules/builder/components/editorRenderingBundle').then(
    (bundle) => bundle.AddElementZone
  )
)
export const AddElementModal = lazyComponent(() =>
  import('@baserow/modules/builder/components/editorRenderingBundle').then(
    (bundle) => bundle.AddElementModal
  )
)
