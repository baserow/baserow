import { ref } from 'vue'
import { useNuxtApp } from '#app'

import JobService from '@baserow/modules/core/services/job'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Downloads the archive of a user template. A click starts the job that prepares
 * the archive, or gets the one that already prepares it, and its toast saves the
 * file when it's ready. The requests are tracked per template, so that one row's
 * request doesn't block or show on another row.
 */
export function useUserTemplateDownload() {
  const { $client, $registry, $store } = useNuxtApp()

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
    try {
      const { data: job } = await JobService($client).create(
        'download_user_template',
        { slug: template.slug, latest }
      )
      // Toast first, so that the job's end finds it to update.
      await $registry
        .get('job', 'download_user_template')
        .addDownloadToast(job, template, { latest })
      await $store.dispatch('job/create', job)
    } catch (error) {
      notifyIf(error, 'template')
    } finally {
      downloadingIds.value.delete(template.id)
    }
    return true
  }

  return { isDownloading, download }
}
