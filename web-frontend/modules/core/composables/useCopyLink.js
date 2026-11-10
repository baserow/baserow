import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

/**
 * Copies a link, then shows the `Copied` component, or an error toast when the
 * browser refuses to copy.
 */
export function useCopyLink() {
  const store = useStore()
  const { $i18n } = useNuxtApp()

  /**
   * @param {string} url The link to copy.
   * @param {object} copied The `Copied` component shown once the link is copied.
   */
  async function copyLink(url, copied) {
    try {
      await copyToClipboard(url)
    } catch {
      store.dispatch('toast/error', { title: $i18n.t('copied.linkFailed') })
      return
    }
    copied?.show()
  }

  return { copyLink }
}
