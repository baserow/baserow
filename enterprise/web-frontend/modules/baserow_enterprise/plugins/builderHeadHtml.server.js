import {
  defineNuxtPlugin,
  useRequestEvent,
  useResponseHeader,
  useRuntimeConfig,
} from '#imports'
import { getBuilderPreviewApiPath } from '@baserow/modules/builder/utils/preview'
import { previewSharesEditorHostname } from '@baserow_enterprise/utils/builderHeadHtml'

export async function fetchBuilderHeadHtml(
  { builder, mode, requestUrl, config, previewSsrCookieHeader },
  fetch = $fetch
) {
  if (builder.untrusted_content || !builder.has_head_html) {
    return ''
  }

  const headers = { Accept: 'application/json' }
  let path
  if (mode === 'preview') {
    if (
      previewSharesEditorHostname(config.public) ||
      requestUrl.origin !== new URL(config.public.builderPreviewUrl).origin ||
      !previewSsrCookieHeader
    ) {
      return ''
    }
    headers.Cookie = previewSsrCookieHeader
    path = getBuilderPreviewApiPath(builder.id, 'custom-code/html/')
  } else if (mode === 'public') {
    path = `custom_code/${builder.id}/html/public/`
  } else {
    return ''
  }

  const backendUrl = config.privateBackendUrl || config.public.publicBackendUrl
  try {
    const data = await fetch(path, {
      baseURL: `${backendUrl.replace(/\/$/, '')}/api/`,
      headers,
      redirect: 'error',
      retry: 0,
      timeout: 2000,
    })
    return typeof data?.html === 'string' ? data.html : ''
  } catch {
    // Custom code is optional. A failed lookup should still render the page.
    return ''
  }
}

export default defineNuxtPlugin({
  name: 'builder-head-html',
  dependsOn: ['builder-preview-client-handler'],
  setup(nuxtApp) {
    const event = useRequestEvent()
    const config = useRuntimeConfig()
    const cacheControl = useResponseHeader('Cache-Control')

    nuxtApp.hook('builder:render', async ({ builder, mode, requestUrl }) => {
      const fragment = await fetchBuilderHeadHtml({
        builder,
        mode,
        requestUrl,
        config,
        previewSsrCookieHeader: nuxtApp.$builderPreviewSsrCookieHeader,
      })
      if (fragment) {
        event.context.baserowBuilderHeadHtml = fragment
        if (mode === 'preview') {
          cacheControl.value = 'private, no-store'
        }
      }
    })
  },
})
