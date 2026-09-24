import { Registerable } from '@baserow/modules/core/registry'
import { getBuilderBreakpoints } from '@baserow/modules/builder/utils/breakpoints'

export class DeviceType extends Registerable {
  get iconClass() {
    return null
  }

  getOrder() {
    return null
  }

  /**
   * @deprecated Implement `getPreviewWidth(builder)` instead.
   */
  get minWidth() {
    return 0
  }

  /**
   * @deprecated Implement `getMaxWidth(builder)` instead.
   */
  get maxWidth() {
    return 0
  }

  /**
   * Returns the width used for this device in the editor preview.
   *
   * @param {Object} builder The application builder being previewed.
   * @returns {number}
   */
  getPreviewWidth(builder) {
    return this.getMinWidth(builder)
  }

  /**
   * @deprecated Implement `getPreviewWidth(builder)` instead.
   */
  getMinWidth() {
    return this.minWidth
  }

  /**
   * Returns the maximum viewport width represented by this device, or `null`
   * when it has no upper bound.
   *
   * @param {Object} builder The application builder being previewed.
   * @returns {number|null}
   */
  getMaxWidth() {
    return this.maxWidth
  }
}

export class DesktopDeviceType extends DeviceType {
  static getType() {
    return 'desktop'
  }

  get iconClass() {
    return 'iconoir-apple-imac-2021'
  }

  getOrder() {
    return 1
  }

  getPreviewWidth(builder) {
    return getBuilderBreakpoints(builder).tablet + 1
  }

  getMaxWidth() {
    return null
  }
}

export class TabletDeviceType extends DeviceType {
  static getType() {
    return 'tablet'
  }

  get iconClass() {
    return 'baserow-icon-tablet'
  }

  getOrder() {
    return 2
  }

  getPreviewWidth(builder) {
    return getBuilderBreakpoints(builder).tablet
  }

  getMaxWidth(builder) {
    return getBuilderBreakpoints(builder).tablet
  }
}

export class SmartphoneDeviceType extends DeviceType {
  static getType() {
    return 'smartphone'
  }

  get iconClass() {
    return 'baserow-icon-smartphone'
  }

  getOrder() {
    return 3
  }

  getPreviewWidth(builder) {
    return getBuilderBreakpoints(builder).mobile
  }

  getMaxWidth(builder) {
    return getBuilderBreakpoints(builder).mobile
  }
}
