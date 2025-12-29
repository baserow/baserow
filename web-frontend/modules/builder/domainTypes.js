import { Registerable } from '@baserow/modules/core/registry'
import CustomDomainDetails from '@baserow/modules/builder/components/domain/CustomDomainDetails'
import CustomDomainForm from '@baserow/modules/builder/components/domain/CustomDomainForm'
import SubDomainForm from '@baserow/modules/builder/components/domain/SubDomainForm'
import SubDomainDetails from '@baserow/modules/builder/components/domain/SubDomainDetails'

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
