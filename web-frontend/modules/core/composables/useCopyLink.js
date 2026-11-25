import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'
import { captureTemplateEvent } from '@baserow/modules/core/utils/templateAnalytics'

/**
 * Copies a template link, then shows the `Copied` component, or an error toast
 * when the browser refuses to copy.
 */
export function useCopyLink() {
  const store = useStore()
  const { $i18n, $posthog } = useNuxtApp()

  /**
   * @param {string} url The link to copy.
   * @param {object} copied The `Copied` component shown once the link is copied.
   * @param {object} template The template the link opens.
   * @param {object} [options]
   * @param {boolean} [options.tracked] Whether the copy is captured.
   */
  async function copyLink(url, copied, template, { tracked = true } = {}) {
    try {
      await copyToClipboard(url)
    } catch {
      store.dispatch('toast/error', {
        title: $i18n.t('copied.linkFailedTitle'),
        message: $i18n.t('copied.linkFailedMessage'),
      })
      return
    }
    copied?.show()
    if (tracked) {
      captureTemplateEvent($posthog, 'link_copied', template)
    }
  }

  return { copyLink }
}
