import { describe, expect, test } from 'vitest'

import {
  getBuilderPreviewCookieName,
  getBuilderPreviewCookiePath,
  getBuilderPreviewSsrCookieName,
  getBuilderPreviewUserSourceCookieName,
} from '@baserow/modules/core/utils/builderPreview'

const config = { public: { baserowFrontendCookiePrefix: 'test_' } }

describe('builder preview cookies', () => {
  test('uses builder-specific names and paths', () => {
    expect(getBuilderPreviewCookieName(config, 42)).toBe(
      'test_baserow_builder_preview_42'
    )
    expect(getBuilderPreviewSsrCookieName(config, 42)).toBe(
      'test_baserow_builder_preview_ssr_42'
    )
    expect(getBuilderPreviewUserSourceCookieName(42)).toBe(
      'user_source_token_42'
    )
    expect(getBuilderPreviewCookiePath(42)).toBe('/builder-preview/42')
  })
})
