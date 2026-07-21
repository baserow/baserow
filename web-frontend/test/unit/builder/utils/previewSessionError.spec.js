import { describe, expect, test, vi } from 'vitest'

import { makeBuilderPreviewSessionErrorInterceptor } from '@baserow/modules/builder/plugins/clientHandler'

const i18n = {
  t: (key) => key,
}

describe('builder preview session response interceptor', () => {
  test('shows a non-reportable error page for an invalid preview session', async () => {
    const showError = vi.fn()
    const interceptor = makeBuilderPreviewSessionErrorInterceptor(
      i18n,
      showError
    )
    const responseError = {
      response: {
        status: 401,
        data: { error: 'ERROR_BUILDER_PREVIEW_SESSION_INVALID' },
      },
    }

    const rejection = interceptor(responseError)

    expect(showError).toHaveBeenCalledOnce()
    const errorPage = showError.mock.calls[0][0]
    await expect(rejection).rejects.toBe(errorPage)
    expect(errorPage.statusCode).toBe(401)
    expect(errorPage.message).toBe('publicPage.previewSessionExpiredTitle')
    expect(errorPage.content).toBe(
      'publicPage.previewSessionExpiredDescription'
    )
    expect(errorPage.data).toEqual({
      report: false,
      error: 'ERROR_BUILDER_PREVIEW_SESSION_INVALID',
    })
    expect(errorPage.fatal).toBe(true)
  })

  test('leaves unrelated authentication errors unchanged', async () => {
    const showError = vi.fn()
    const interceptor = makeBuilderPreviewSessionErrorInterceptor(
      i18n,
      showError
    )
    const responseError = {
      response: {
        status: 401,
        data: { error: 'ERROR_INVALID_ACCESS_TOKEN' },
      },
    }

    await expect(interceptor(responseError)).rejects.toBe(responseError)
    expect(showError).not.toHaveBeenCalled()
  })
})
