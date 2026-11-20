import {
  LocalBaserowNodeType,
  NodeType,
} from '@baserow/modules/automation/nodeTypes'
import { ActionNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'
import { LocalBaserowSemanticSearchServiceType } from '@baserow_enterprise/integrations/localBaserow/serviceTypes'
import { MicrosoftTeamsWriteMessageServiceType } from '@baserow_enterprise/integrations/microsoftTeams/serviceTypes'

export class CoreCodeActionNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'code'
  }

  isInError(context) {
    return (
      Boolean(context.workflow?.untrusted_content) || super.isInError(context)
    )
  }

  getErrorMessage(context) {
    if (context.workflow?.untrusted_content) {
      return this.app.$i18n.t('automationHeader.untrustedContentWarning')
    }
    return super.getErrorMessage(context)
  }

  getOrder() {
    return 6.4
  }

  get name() {
    return this.app.$i18n.t('nodeType.codeLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreCodeServiceType.getType())
  }
}

export class CoreXLSFileReaderActionNodeType extends ActionNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'xls_file_reader'
  }

  getOrder() {
    return 10
  }

  get name() {
    return this.app.$i18n.t('nodeType.xlsFileReaderLabel')
  }

  get dataType() {
    return 'array'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreXLSFileReaderServiceType.getType()
    )
  }
}

export class LocalBaserowSemanticSearchActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_semantic_search'
  }

  getOrder() {
    return 5.5
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowSemanticSearchLabel'
  }

  get dataType() {
    return 'array'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowSemanticSearchServiceType.getType()
    )
  }
}

export class MicrosoftTeamsWriteMessageActionNodeType extends ActionNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'microsoft_teams_write_message'
  }

  getOrder() {
    return 91
  }

  get name() {
    return this.app.$i18n.t('nodeType.microsoftTeamsWriteMessageName')
  }

  getDefaultLabel({ node }) {
    const label = node?.service?.destination_label
    return label
      ? this.app.$i18n.t('nodeType.microsoftTeamsWriteMessageLabel', {
          destination: label,
        })
      : this.name
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      MicrosoftTeamsWriteMessageServiceType.getType()
    )
  }
}
