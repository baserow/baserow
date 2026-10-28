import { NodeType } from '@baserow/modules/automation/nodeTypes'
import { ActionNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'

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
