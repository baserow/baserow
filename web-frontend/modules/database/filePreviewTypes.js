import { Registerable } from '@baserow/modules/core/registry'
import PreviewImage from '@baserow/modules/database/components/preview/PreviewImage'
import PreviewVideo from '@baserow/modules/database/components/preview/PreviewVideo'
import PreviewAudio from '@baserow/modules/database/components/preview/PreviewAudio'
import PreviewPDFBrowser from '@baserow/modules/database/components/preview/PreviewPDFBrowser'
import PreviewGoogleDocs from '@baserow/modules/database/components/preview/PreviewGoogleDocs'

export class FilePreviewType extends Registerable {
  /**
   * Should return true if the preview type is compatible with the file.
   * @param {string} mimeType of the file
   * @param {sting} url of the file
   * @returns whether the preview type is compatible with the file
   */
  isCompatible(mimeType, url) {
    throw new Error(
      'Not implement error. This file preview type should return a boolean.'
    )
  }

  /**
   * @returns the preview component
   */
  getPreviewComponent() {
    return null
  }

  getOrder() {
    return 50
  }

  getName() {
    return null
  }

  isExternal() {
    return false
  }
}

export class ImageFilePreview extends FilePreviewType {
  static getType() {
    return 'image'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('previewType.imageBrowser')
  }

  isCompatible(mimeType, fileName) {
    return mimeType.startsWith('image/') && mimeType !== 'image/psd'
  }

  getPreviewComponent() {
    return PreviewImage
  }
}

export class VideoFilePreview extends FilePreviewType {
  static getType() {
    return 'video'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('previewType.videoBrowser')
  }

  isCompatible(mimeType, fileName) {
    return mimeType.startsWith('video/')
  }

  getPreviewComponent() {
    return PreviewVideo
  }
}

export class AudioFilePreview extends FilePreviewType {
  static getType() {
    return 'audio'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('previewType.audioBrowser')
  }

  isCompatible(mimeType, fileName) {
    return mimeType.startsWith('audio/')
  }

  getPreviewComponent() {
    return PreviewAudio
  }
}

export class PDFBrowserFilePreview extends FilePreviewType {
  static getType() {
    return 'pdf-browser'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('previewType.pdfBrowser')
  }

  isCompatible(mimeType, fileName) {
    return mimeType === 'application/pdf'
  }

  getPreviewComponent() {
    return PreviewPDFBrowser
  }
}

export class GoogleDocFilePreview extends FilePreviewType {
  static getType() {
    return 'google-docs'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('previewType.googleDocs')
  }

  isCompatible(mimeType, fileName) {
    if (this.app.$config.BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW) {
      return false
    }

    const conds = [
      'application/pdf',

      /ms-?word/,
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',

      /ms-?powerpoint/,
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',

      /ms-?excel/,
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ]
    return conds.some((cond) => {
      if (cond instanceof RegExp) {
        return cond.test(mimeType)
      } else if (cond === undefined) {
        return true
      } else {
        return mimeType === cond
      }
    })
  }

  getPreviewComponent() {
    return PreviewGoogleDocs
  }

  isExternal() {
    return true
  }
}
