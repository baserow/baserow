export const LEGACY_BUILDER_BREAKPOINTS = Object.freeze({
  mobile: 500,
  tablet: 768,
})

export const MIN_BUILDER_BREAKPOINT = 320
export const MAX_BUILDER_BREAKPOINT = 1920

export function getBuilderBreakpoints(builder) {
  const { mobile, tablet } = builder.breakpoints || {}

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
