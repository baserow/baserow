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
