/**
 * Head HTML is only rendered in Preview when Preview runs on its own hostname.
 * Cookies are scoped by hostname, not port, so a shared hostname would expose
 * the editor's cookies to the HTML. An invalid URL counts as shared.
 *
 * @param {object} publicConfig The public runtime config.
 * @returns {boolean} Whether Preview shares the editor's hostname.
 */
export const previewSharesEditorHostname = (publicConfig) => {
  try {
    return (
      new URL(publicConfig.builderPreviewUrl).hostname ===
      new URL(publicConfig.publicWebFrontendUrl).hostname
    )
  } catch {
    return true
  }
}
