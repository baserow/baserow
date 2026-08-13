// Extra URI schemes accepted for links on top of TipTap's defaults (http,
// https). Shared by the link mark and the image extension's link fallback.
export const LINK_PROTOCOLS = [
  { scheme: 'ftp' },
  { scheme: 'mailto', optionalSlashes: true },
  { scheme: 'tel', optionalSlashes: true },
]
