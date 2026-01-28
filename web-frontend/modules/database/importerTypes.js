import { Registerable } from '@baserow/modules/core/registry'

import TableCSVImporter from '@baserow/modules/database/components/table/TableCSVImporter'
import TablePasteImporter from '@baserow/modules/database/components/table/TablePasteImporter'
import TableXMLImporter from '@baserow/modules/database/components/table/TableXMLImporter'
import TableJSONImporter from '@baserow/modules/database/components/table/TableJSONImporter'

export class ImporterType extends Registerable {
  /**
   * Should return a icon class name class name related to the icon that must be displayed
   * to the user.
   */
  getIconClass() {
    throw new Error('The icon class of an importer type must be set.')
  }

  /**
   * Should return a human readable name that indicating what the importer does.
   */
  getName() {
    throw new Error('The name of an importer type must be set.')
  }

  /**
   * Should return the component that is added to the CreateTableModal when the
   * importer is chosen. It should handle all the user input and additional form
   * fields and it should generate a compatible data object that must be added to
   * the form values.
   */
  getFormComponent() {
    return null
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of an importer type must be set.')
    }
  }

  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
    }
  }
}

export class CSVImporterType extends ImporterType {
  static getType() {
    return 'baserow-icon-file-csv'
  }

  getIconClass() {
    return 'baserow-icon-file-csv'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('importerType.csv')
  }

  getFormComponent() {
    return TableCSVImporter
  }
}

export class PasteImporterType extends ImporterType {
  static getType() {
    return 'paste'
  }

  getIconClass() {
    return 'iconoir-paste-clipboard'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('importerType.paste')
  }

  getFormComponent() {
    return TablePasteImporter
  }
}

export class XMLImporterType extends ImporterType {
  static getType() {
    return 'xml'
  }

  getIconClass() {
    return 'baserow-icon-file-code'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('importerType.xml')
  }

  getFormComponent() {
    return TableXMLImporter
  }
}

export class JSONImporterType extends ImporterType {
  static getType() {
    return 'json'
  }

  getIconClass() {
    return 'baserow-icon-file-code'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('importerType.json')
  }

  getFormComponent() {
    return TableJSONImporter
  }
}
