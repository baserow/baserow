import { ref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { signedInUserCheck } from '@baserow/modules/core/utils/auth'

/**
 * Downloads the archive of a user template. A click gets the archive when it's
 * ready, or the job that builds it, whose toast saves the file once it's built.
 * The requests are tracked per template, so that one row's request doesn't block
 * or show on another row. An answer that comes after a logout shows nothing.
 */
export function useUserTemplateDownload() {
  const store = useStore()
  const { $client, $registry } = useNuxtApp()

  // The ids of the templates whose download is being requested.
  const downloadingIds = ref(new Set())

  function isDownloading(template) {
    return downloadingIds.value.has(template.id)
  }

  /**
   * @returns {Promise<boolean>} False only for a repeat click while requesting,
   *   so that the menu stays open.
   */
  async function download(template, { latest = false } = {}) {
    if (isDownloading(template)) {
      return false
    }
    downloadingIds.value.add(template.id)
    const isSameUser = signedInUserCheck(store)
    try {
      const response = await TemplateService($client).download(template.slug, {
        latest,
      })
      if (!isSameUser()) {
        return true
      }
      await $registry
        .get('job', 'download_user_template')
        .startDownload(response, template, { latest })
    } catch (error) {
      if (isSameUser()) {
        notifyIf(error, 'template')
      }
    } finally {
      downloadingIds.value.delete(template.id)
    }
    return true
  }

  return { isDownloading, download }
}
