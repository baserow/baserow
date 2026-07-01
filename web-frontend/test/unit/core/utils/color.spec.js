import {
  resolveColor,
  colorRecommendation,
  conversionsMap,
  colorContrast,
} from '@baserow/modules/core/utils/colors'

describe('colorUtils', () => {
  test('resolve', () => {
    expect(resolveColor('#00000000', [])).toBe('#00000000')
    expect(resolveColor('test', [])).toBe('test')
    expect(
      resolveColor('primary', [
        { name: 'Primary', value: 'primary', color: '#ff000000' },
      ])
    ).toBe('#ff000000')
    expect(
      resolveColor('secondary', [
        { name: 'Primary', value: 'primary', color: '#ff000000' },
      ])
    ).toBe('secondary')
    expect(
      resolveColor('#00000042', [
        { name: 'Default', value: '#00000042', color: '#00000042' },
      ])
    ).toBe('#00000042')
  })

  test('colorRecommendation', () => {
    expect(colorRecommendation('#FFFFFF')).toBe('gray')
    expect(colorRecommendation('#000000')).toBe('gray')
    expect(colorRecommendation('#FFFFFFFF')).toBe('gray')
    expect(colorRecommendation('#000000FF')).toBe('gray')
    expect(colorRecommendation('#5498db')).toBe('black')
    expect(colorRecommendation('#2c3e50')).toBe('white')
  })

  test('convert hex to oklch', () => {
    const oklchColor = conversionsMap.hex.oklch('#ff0000ff')

    expect(oklchColor.l).toBeCloseTo(0.62796, 5)
    expect(oklchColor.c).toBeCloseTo(0.25768, 5)
    expect(oklchColor.h).toBeCloseTo(0.08121, 5)
    expect(oklchColor.a).toBeCloseTo(1, 5)
  })

  test('convert oklch to hex', () => {
    expect(
      conversionsMap.oklch.hex({
        l: 0.62796,
        c: 0.25768,
        h: 0.08121,
        a: 1,
      })
    ).toBe('#ff0000ff')
  })

  test('round trip hex and oklch conversion', () => {
    const hexColor = '#5498dbcc'
    expect(conversionsMap.oklch.hex(conversionsMap.hex.oklch(hexColor))).toBe(
      hexColor
    )
  })

  test('colorContrast adjusts perceptual lightness using oklch', () => {
    expect(colorContrast('#5498dbff')).toBe('#4588caff')
    expect(colorContrast('#2c3e50ff')).toBe('#394b5eff')
    expect(colorContrast('#5498dbcc')).toBe('#4588cacc')
  })

  test('colorContrast keeps black hover colors visibly different', () => {
    expect(colorContrast('#000000ff')).toBe('#0b0b0bff')
    expect(colorContrast('#00000000')).toBe('#0b0b0b00')
  })
})
