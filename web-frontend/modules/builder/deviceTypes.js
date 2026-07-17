import { Registerable } from '@baserow/modules/core/registry'
import { getBuilderBreakpoints } from '@baserow/modules/builder/utils/breakpoints'

export class DeviceType extends Registerable {
  get iconClass() {
    return null
  }

  getOrder() {
    return null
  }

  get minWidth() {
    return 0
  }

  get maxWidth() {
    return 0
  }

  getMinWidth(builder) {
    return this.minWidth
  }

  getMaxWidth(builder) {
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

  get minWidth() {
    return 1100
  }

  get maxWidth() {
    return null // Can be as wide as you want
  }

  getMinWidth(builder) {
    return getBuilderBreakpoints(builder).tablet + 1
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

  get minWidth() {
    return 768
  }

  get maxWidth() {
    return 768
  }

  getMinWidth(builder) {
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

  get minWidth() {
    return 500
  }

  get maxWidth() {
    return 500
  }

  getMinWidth(builder) {
    return getBuilderBreakpoints(builder).mobile
  }

  getMaxWidth(builder) {
    return getBuilderBreakpoints(builder).mobile
  }
}
