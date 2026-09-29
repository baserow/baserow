import { describe, expect, test } from 'vitest'

import {
  LEGACY_BUILDER_BREAKPOINTS,
  getBuilderBreakpoints,
} from '@baserow/modules/builder/utils/breakpoints'

describe('builder breakpoints', () => {
  test('uses legacy breakpoints when they are not explicitly configured', () => {
    expect(
      getBuilderBreakpoints({
        breakpoints: {},
      })
    ).toBe(LEGACY_BUILDER_BREAKPOINTS)
    expect(getBuilderBreakpoints({})).toBe(LEGACY_BUILDER_BREAKPOINTS)
  })

  test('uses explicitly configured breakpoints', () => {
    const builder = { breakpoints: { mobile: 640, tablet: 1024 } }

    expect(getBuilderBreakpoints(builder)).toEqual({
      mobile: 640,
      tablet: 1024,
    })
  })
})
