export const LEGACY_BUILDER_BREAKPOINTS = Object.freeze({
  mobile: 500,
  tablet: 768,
})

export function getBuilderBreakpoints(builder) {
  const { mobile_breakpoint: mobile, tablet_breakpoint: tablet } = builder

  if (
    mobile === null ||
    mobile === undefined ||
    tablet === null ||
    tablet === undefined
  ) {
    return LEGACY_BUILDER_BREAKPOINTS
  }

  return { mobile, tablet }
}

export function getBuilderResponsiveStyles(builder) {
  const { mobile, tablet } = getBuilderBreakpoints(builder)

  return `
    @media (min-width: ${tablet + 1}px) {
      .column-element--public.column-element--stack-desktop {
        grid-template-columns: 1fr;
      }
    }

    @media (min-width: ${mobile + 1}px) and (max-width: ${tablet}px) {
      .column-element--public.column-element--stack-tablet {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: ${mobile}px) {
      .column-element--public.column-element--stack-smartphone {
        grid-template-columns: 1fr;
      }
    }
  `
}
