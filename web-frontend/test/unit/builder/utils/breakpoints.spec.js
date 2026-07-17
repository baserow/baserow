import { describe, expect, test } from 'vitest'

import {
  LEGACY_BUILDER_BREAKPOINTS,
  getBuilderBreakpoints,
  getBuilderResponsiveStyles,
} from '@baserow/modules/builder/utils/breakpoints'

describe('builder breakpoints', () => {
  test('uses legacy breakpoints when they are not explicitly configured', () => {
    expect(
      getBuilderBreakpoints({
        mobile_breakpoint: null,
        tablet_breakpoint: null,
      })
    ).toBe(LEGACY_BUILDER_BREAKPOINTS)
    expect(getBuilderBreakpoints({})).toBe(LEGACY_BUILDER_BREAKPOINTS)
  })

  test('uses explicitly configured breakpoints and generates their media queries', () => {
    const builder = { mobile_breakpoint: 640, tablet_breakpoint: 1024 }

    expect(getBuilderBreakpoints(builder)).toEqual({
      mobile: 640,
      tablet: 1024,
    })
    expect(getBuilderResponsiveStyles(builder)).toContain(
      '@media (min-width: 1025px)'
    )
    expect(getBuilderResponsiveStyles(builder)).toContain(
      '@media (min-width: 641px) and (max-width: 1024px)'
    )
    expect(getBuilderResponsiveStyles(builder)).toContain(
      '@media (max-width: 640px)'
    )
  })
})
