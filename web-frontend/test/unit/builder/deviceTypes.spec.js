import { describe, expect, test } from 'vitest'

import {
  DesktopDeviceType,
  SmartphoneDeviceType,
  TabletDeviceType,
} from '@baserow/modules/builder/deviceTypes'

describe('builder device types', () => {
  test('uses the builder breakpoints for editor preview widths', () => {
    const builder = { breakpoints: { mobile: 640, tablet: 1024 } }

    expect(new SmartphoneDeviceType().getMinWidth(builder)).toBe(640)
    expect(new SmartphoneDeviceType().getMaxWidth(builder)).toBe(640)
    expect(new TabletDeviceType().getMinWidth(builder)).toBe(1024)
    expect(new TabletDeviceType().getMaxWidth(builder)).toBe(1024)
    expect(new DesktopDeviceType().getMinWidth(builder)).toBe(1025)
    expect(new DesktopDeviceType().getMaxWidth(builder)).toBeNull()
  })
})
