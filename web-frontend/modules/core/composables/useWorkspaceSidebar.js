import { inject, provide, ref } from 'vue'

export const workspaceSidebarVisibleKey = Symbol('workspaceSidebarVisible')

/**
 * Tells the components of the `app` layout whether the sidebar lists the
 * applications and the pending jobs of the selected workspace, which it only
 * does when it's the workspace sidebar and it isn't collapsed.
 *
 * @param {import('vue').Ref<boolean>} visible
 */
export function provideWorkspaceSidebarVisible(visible) {
  provide(workspaceSidebarVisibleKey, visible)
}

/**
 * @returns {import('vue').Ref<boolean>} Whether the sidebar of the selected
 *   workspace shows. Always false outside of the `app` layout.
 */
export function injectWorkspaceSidebarVisible() {
  return inject(workspaceSidebarVisibleKey, () => ref(false), true)
}
