import type { Response } from '@playwright/test'

import { createBuilderElement } from '../../fixtures/builder/builderElement'
import { baserowConfig } from '../../playwright.config'
import { expect, test } from '../baserowTest'

test.describe('Builder preview test suite', () => {
  test('Renders content and missing-page errors during SSR', async ({
    page,
    context,
    builderPagePage,
  }) => {
    const previewContent = 'SSR preview content'
    await createBuilderElement(builderPagePage.builderPage, 'heading', {
      value: `'${previewContent}'`,
    })
    await builderPagePage.goto()

    const documentResponses: Response[] = []
    const captureDocumentResponse = (response: Response) => {
      if (response.request().resourceType() === 'document') {
        documentResponses.push(response)
      }
    }
    context.on('response', captureDocumentResponse)

    try {
      const previewPagePromise = context.waitForEvent('page')
      await page.getByRole('button', { name: 'Preview' }).click()
      const previewPage = await previewPagePromise
      await previewPage.waitForLoadState('domcontentloaded')

      const previewOrigin = new URL(baserowConfig.BUILDER_PREVIEW_URL).origin
      const finalDocumentResponse = documentResponses.findLast((response) => {
        const url = new URL(response.url())
        return url.origin === previewOrigin && url.search === ''
      })
      if (!finalDocumentResponse) {
        const lastDocumentBody = await documentResponses.at(-1)?.text()
        const errorTitle = lastDocumentBody?.match(/<title>(.*?)<\/title>/)?.[1]
        throw new Error(
          `The clean preview document response was not received. Documents: ${documentResponses
            .map((response) => {
              const url = new URL(response.url())
              return `${response.status()} ${url.origin}${url.pathname}`
            })
            .join(', ')}. Error title: ${errorTitle}`
        )
      }

      expect(finalDocumentResponse.status()).toBe(200)
      const initialHtml = await finalDocumentResponse.text()
      expect(initialHtml).toContain('<title>Default page</title>')
      expect(initialHtml).toContain(previewContent)
      await expect(previewPage).toHaveTitle('Default page')
      await expect(previewPage.getByText(previewContent)).toBeVisible()

      const previewPathPrefix =
        previewOrigin === new URL(baserowConfig.PUBLIC_WEB_FRONTEND_URL).origin
          ? '/builder-preview'
          : ''
      const missingPageResponse = await previewPage.goto(
        `${previewOrigin}${previewPathPrefix}/missing-page`
      )
      expect(missingPageResponse?.status()).toBe(404)
      expect(await missingPageResponse?.text()).toContain('Page not found')
      await expect(previewPage.getByText('Page not found')).toBeVisible()
    } finally {
      context.off('response', captureDocumentResponse)
    }
  })
})
