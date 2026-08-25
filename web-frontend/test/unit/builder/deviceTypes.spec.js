import { describe, expect, test } from 'vitest'

import {
  DesktopDeviceType,
  DeviceType,
  SmartphoneDeviceType,
  TabletDeviceType,
} from '@baserow/modules/builder/deviceTypes'

describe('builder device types', () => {
  test('uses the builder breakpoints for editor preview widths', () => {
    const builder = { breakpoints: { mobile: 640, tablet: 1024 } }

    expect(new SmartphoneDeviceType().getPreviewWidth(builder)).toBe(640)
    expect(new SmartphoneDeviceType().getMaxWidth(builder)).toBe(640)
    expect(new TabletDeviceType().getPreviewWidth(builder)).toBe(1024)
    expect(new TabletDeviceType().getMaxWidth(builder)).toBe(1024)
    expect(new DesktopDeviceType().getPreviewWidth(builder)).toBe(1025)
    expect(new DesktopDeviceType().getMaxWidth(builder)).toBeNull()
  })

  test('keeps legacy minWidth and maxWidth extensions compatible', () => {
    class LegacyDeviceType extends DeviceType {
      get minWidth() {
        return 500
      }

      get maxWidth() {
        return 768
      }
    }

    const deviceType = new LegacyDeviceType()

    expect(deviceType.getPreviewWidth({})).toBe(500)
    expect(deviceType.getMaxWidth({})).toBe(768)
  })

  test('uses a legacy getMinWidth extension for the preview width', () => {
    class LegacyDeviceType extends DeviceType {
      getMinWidth(builder) {
        return builder.breakpoints.mobile
      }
    }

    expect(
      new LegacyDeviceType().getPreviewWidth({
        breakpoints: { mobile: 640 },
      })
    ).toBe(640)
  })
})
