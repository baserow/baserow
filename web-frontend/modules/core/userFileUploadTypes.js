import { Registerable } from '@baserow/modules/core/registry'
import UploadFileUserFileUpload from '@baserow/modules/core/components/files/UploadFileUserFileUpload'
import UploadViaURLUserFileUpload from '@baserow/modules/core/components/files/UploadViaURLUserFileUpload'

/**
 * Upload file types will be added to the user files modal. Each upload should be able
 * to upload files in a specific way to the user files.
 */
export class UserFileUploadType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize user file upload types. The icon will for example be displayed in the
   * user files modal sidebar. If you for example want the database icon, you must
   * return 'database' here. This will result in the classname 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the user file upload type. This will be shown in the
   * user files modal sidebar.
   */
  getName() {
    return null
  }

  /**
   * The component will be rendered when the user clicks on the item in the user
   * file upload model.
   */
  getComponent() {
    throw new Error('The component of a user file upload type must be set.')
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of a user file upload type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of a user file upload type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a user file upload type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
    }
  }
}

export class UploadFileUserFileUploadType extends UserFileUploadType {
  static getType() {
    return 'file'
  }

  getIconClass() {
    return 'iconoir-upload'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('userFileUploadType.file')
  }

  getComponent() {
    return UploadFileUserFileUpload
  }
}

export class UploadViaURLUserFileUploadType extends UserFileUploadType {
  static getType() {
    return 'url'
  }

  getIconClass() {
    return 'iconoir-link'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('userFileUploadType.url')
  }

  getComponent() {
    return UploadViaURLUserFileUpload
  }
}
