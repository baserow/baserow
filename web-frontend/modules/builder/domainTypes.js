import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'

const CustomDomainDetails = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/builder/components/domain/CustomDomainDetails'),
  hydrate: hydrateOnIdle(),
})
const CustomDomainForm = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/builder/components/domain/CustomDomainForm'),
  hydrate: hydrateOnIdle(),
})
const SubDomainForm = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/builder/components/domain/SubDomainForm'),
  hydrate: hydrateOnIdle(),
})
const SubDomainDetails = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/builder/components/domain/SubDomainDetails'),
  hydrate: hydrateOnIdle(),
})

export class DomainType extends Registerable {
  get name() {
    return null
  }

  get detailsComponent() {
    return null
  }

  get formComponent() {
    return null
  }

  get options() {
    return []
  }
}

export class CustomDomainType extends DomainType {
  static getType() {
    return 'custom'
  }

  get name() {
    return this.app.$i18n.t('domainTypes.customName')
  }

  get detailsComponent() {
    return CustomDomainDetails
  }

  get formComponent() {
    return CustomDomainForm
  }

  get options() {
    return [
      {
        name: this.app.$i18n.t('domainTypes.customName'),
        value: {
          type: this.getType(),
          domain: 'custom',
        },
      },
    ]
  }
}

export class SubDomainType extends DomainType {
  static getType() {
    return 'sub_domain'
  }

  get name() {
    return this.app.$i18n.t('domainTypes.subDomainName')
  }

  get options() {
    const domains = this.app.$config.public.baserowBuilderDomains ?? []
    return domains.map((domain) => ({
      name: this.app.$i18n.t('domainTypes.subDomain', { domain }),
      value: {
        type: this.getType(),
        domain,
      },
    }))
  }

  get detailsComponent() {
    return SubDomainDetails
  }

  get formComponent() {
    return SubDomainForm
  }
}
