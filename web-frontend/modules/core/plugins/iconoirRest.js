import { useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  const url = useRuntimeConfig().public.iconoirRestCssUrl
  if (!url) {
    return
  }
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = url
  document.head.appendChild(link)
})
