import { NodeType } from '@baserow/modules/automation/nodeTypes'
import { ActionNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'

export class CoreCodeNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'code'
  }

  getOrder() {
    return 6
  }

  get name() {
    return this.app.$i18n.t('nodeType.codeLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreCodeServiceType.getType())
  }

  isDeactivatedReason({ workspace }) {
    if (
      !this.app.$hasFeature(EnterpriseFeaturesObject.CODE_RUNNER, workspace.id)
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }
}

export class CoreXLSFileReaderNodeType extends ActionNodeTypeMixin(NodeType) {
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

  isDeactivatedReason({ workspace }) {
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.XLS_FILE_READER,
        workspace.id
      )
    ) {
      return this.app.$i18n.t('enterprise.enterpriseOnlyDeactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }
}
