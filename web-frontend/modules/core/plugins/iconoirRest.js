import { useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  const url = useRuntimeConfig().public.iconoirRestCssUrl
  if (!url) {
    return
  }
  // Static icons are in the initial stylesheet; load the remaining catalog here
  // so backend-provided icon names still render without blocking initial CSS.
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = url
  document.head.appendChild(link)
})
