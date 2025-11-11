import {
  ElementType,
  FormElementType,
} from '@baserow/modules/builder/elementTypes'
import AuthFormElement from '@baserow_enterprise/builder/components/elements/AuthFormElement'
import AuthFormElementForm from '@baserow_enterprise/builder/components/elements/AuthFormElementForm'
import FileInputElement from '@baserow_enterprise/builder/components/elements/FileInputElement'
import FileInputElementForm from '@baserow_enterprise/builder/components/elements/FileInputElementForm'
import { uuid } from '@baserow/modules/core/utils/string'
import {
  ensureArray,
  ensureString,
} from '@baserow/modules/core/utils/validator'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { BuilderFileInputElementPaidFeature } from '@baserow_enterprise/paidFeatures'

import { AfterLoginEvent } from '@baserow/modules/builder/eventTypes'

import elementImageAuthForm from '@baserow_enterprise/assets/images/builder/element-auth_form.svg'
import elementImageFileInput from '@baserow_enterprise/assets/images/builder/element-file_input.svg'

import EnterpriseFeaturesObject from '@baserow_enterprise/features'

export class AuthFormElementType extends ElementType {
  static getType() {
    return 'auth_form'
  }

  get name() {
    return this.app.i18n.t('elementType.authForm')
  }

  get description() {
    return this.app.i18n.t('elementType.authFormDescription')
  }

  get iconClass() {
    return 'iconoir-log-in'
  }

  get image() {
    return elementImageAuthForm
  }

  get component() {
    return AuthFormElement
  }

  get generalFormComponent() {
    return AuthFormElementForm
  }

  getEvents(element) {
    return [new AfterLoginEvent({ app: this.app })]
  }

  getErrorMessage(element, applicationContext) {
    const { builder } = applicationContext

    if (!element.user_source_id) {
      return this.$t('elementType.errorUserSourceMissing')
    }
    const userSource = this.app.store.getters['userSource/getUserSourceById'](
      builder,
      element.user_source_id
    )
    if (!userSource) {
      return this.$t('elementType.errorUserSourceMissing')
    }
    const userSourceType = this.app.$registry.get('userSource', userSource.type)
    const loginOptions = userSourceType.getLoginOptions(userSource)

    const hasLoginOptions = Object.keys(loginOptions).length !== 0

    if (!hasLoginOptions) {
      return this.app.i18n.t('elementType.errorUserSourceHasNoLoginOption')
    }

    return super.getErrorMessage(element, applicationContext)
  }
}

export class FileInputElementType extends FormElementType {
  static getType() {
    return 'input_file'
  }

  static getError(element, value, applicationContext) {
    const arrayValue = element.multiple ? value : value ? [value] : []

    if (element.required && arrayValue.length === 0) {
      return 'required'
    }

    if (
      arrayValue.some(({ size }) => {
        return (
          typeof size === 'number' &&
          size / (1024 * 1024) >= element.max_filesize
        )
      })
    ) {
      return 'fileSize'
    }

    return null
  }

  isValid(element, value, applicationContext) {
    return (
      FileInputElementType.getError(element, value, applicationContext) === null
    )
  }

  get name() {
    return this.app.i18n.t('elementType.fileInput')
  }

  get description() {
    return this.app.i18n.t('elementType.fileInputDescription')
  }

  get iconClass() {
    return 'iconoir-input-field'
  }

  get image() {
    return elementImageFileInput
  }

  get component() {
    return FileInputElement
  }

  get generalFormComponent() {
    return FileInputElementForm
  }

  formDataType(element) {
    if (element.multiple) {
      return 'array'
    }
    return 'file'
  }

  getDataSchema(element) {
    const type = this.formDataType(element)
    if (type === 'file') {
      return {
        type: 'file',
      }
    } else if (type === 'array') {
      return {
        type: 'array',
        items: {
          type: 'file',
        },
      }
    }
  }

  /**
   * We extract the files from the file input element to the context.
   * @param {*} element
   * @param {*} value
   * @param {*} files
   * @returns
   */
  beforeActionDispatchContext(element, value, files) {
    const withoutFiles = (element.multiple ? value : [value]).map((v) => {
      if (v?.__file__) {
        const data = v.data
        const uid = uuid()
        // Add file to context
        files[uid] = data
        return { ...v, file: uid, data: undefined }
      } else {
        return v
      }
    })

    return element.multiple ? withoutFiles : withoutFiles[0]
  }

  _getName(name, url) {
    if (!name) {
      try {
        const parsedUrl = new URL(url)
        const segments = parsedUrl.pathname.split('/').filter(Boolean) // Remove empty segments
        return segments.at(-1)
      } catch {
        return name
      }
    } else {
      return name
    }
  }

  getInitialFormDataValue(element, applicationContext) {
    try {
      const resolvedNames = this.resolveFormula(element.default_name, {
        element,
        ...applicationContext,
      })
      const resolvedUrls = this.resolveFormula(element.default_url, {
        element,
        ...applicationContext,
      })
      if (element.multiple) {
        const names = ensureArray(resolvedNames).map(ensureString)
        const urls = ensureArray(resolvedUrls).map(ensureString)
        return urls.map((url, index) => {
          return { __file__: true, name: this._getName(names[index], url), url }
        })
      } else {
        const name = ensureString(resolvedNames)
        const url = ensureString(resolvedUrls)
        if (url) {
          return { __file__: true, name: this._getName(name, url), url }
        }
      }
    } catch {
      return element.multiple ? [] : null
    }
  }

  isDeactivatedReason({ workspace }) {
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.BUILDER_FILE_INPUT,
        workspace.id
      )
    ) {
      return this.app.i18n.t('enterprise.deactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }

  getDeactivatedClickModal({ workspace }) {
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.BUILDER_FILE_INPUT,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        {
          'initial-selected-type': BuilderFileInputElementPaidFeature.getType(),
        },
      ]
    }
    return null
  }
}
