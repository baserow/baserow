import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { ErrorPageType } from '@baserow/modules/core/errorPageTypes'

const PublicSiteErrorPage = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/builder/components/PublicSiteErrorPage'),
  hydrate: hydrateOnIdle(),
})

export class PublicSiteErrorPageType extends ErrorPageType {
  getComponent() {
    return PublicSiteErrorPage
  }

  isApplicable() {
    return (
      this.app.$router.currentRoute.value.name === 'application-builder-page' ||
      this.app.$router.currentRoute.value.name === 'application-builder-preview'
    )
  }

  static getType() {
    return 'publicSite'
  }

  getOrder() {
    return 10
  }
}
