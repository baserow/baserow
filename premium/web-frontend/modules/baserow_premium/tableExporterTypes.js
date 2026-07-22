import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { TableExporterType } from '@baserow/modules/database/exporterTypes'
import { GridViewType } from '@baserow/modules/database/viewTypes'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { ExportsPaidFeature } from '@baserow_premium/paidFeatures'

const TableJSONExporter = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/exporter/TableJSONExporter'),
  hydrate: hydrateOnIdle(),
})
const TableXMLExporter = defineAsyncComponent({
  loader: () => import('@baserow_premium/components/exporter/TableXMLExporter'),
  hydrate: hydrateOnIdle(),
})
const TableExcelExporter = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/exporter/TableExcelExporter'),
  hydrate: hydrateOnIdle(),
})
const TableFileExporter = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/exporter/TableFileExporter'),
  hydrate: hydrateOnIdle(),
})

class PremiumTableExporterType extends TableExporterType {
  getDeactivatedText() {
    return this.app.$i18n.t('premium.deactivated')
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': ExportsPaidFeature.getType() },
    ]
  }

  isDeactivated(workspaceId) {
    // If the user is looking a publicly shared view, then the feature must never be
    // deactivated because the check can't be done properly.
    const isPublic = this.app.$store.getters['page/view/public/getIsPublic']
    return (
      !this.app.$hasFeature(PremiumFeatures.PREMIUM, workspaceId) && !isPublic
    )
  }
}

export class JSONTableExporter extends PremiumTableExporterType {
  static getType() {
    return 'json'
  }

  getIconClass() {
    return 'baserow-icon-file-code'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('premium.exporterType.json')
  }

  getFormComponent() {
    return TableJSONExporter
  }

  getCanExportTable() {
    return true
  }

  getSupportedViews() {
    return [GridViewType.getType()]
  }
}

export class XMLTableExporter extends PremiumTableExporterType {
  static getType() {
    return 'xml'
  }

  getIconClass() {
    return 'baserow-icon-file-code'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('premium.exporterType.xml')
  }

  getFormComponent() {
    return TableXMLExporter
  }

  getCanExportTable() {
    return true
  }

  getSupportedViews() {
    return [GridViewType.getType()]
  }
}

export class ExcelTableExporterType extends PremiumTableExporterType {
  static getType() {
    return 'excel'
  }

  getFileExtension() {
    return 'xlsx'
  }

  getIconClass() {
    return 'baserow-icon-file-excel'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('premium.exporterType.excel')
  }

  getFormComponent() {
    return TableExcelExporter
  }

  getCanExportTable() {
    return true
  }

  getSupportedViews() {
    return [GridViewType.getType()]
  }
}

export class FileTableExporter extends PremiumTableExporterType {
  static getType() {
    return 'file'
  }

  getFileExtension() {
    return 'zip'
  }

  getIconClass() {
    return 'baserow-icon-file-code'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('premium.exporterType.file')
  }

  getFormComponent() {
    return TableFileExporter
  }

  getCanExportTable() {
    return true
  }

  getSupportedViews() {
    return [GridViewType.getType()]
  }
}
