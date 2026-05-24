import {
  getColorClass,
  resolveColor,
  colorRecommendation,
} from '@baserow/modules/core/utils/colors'

describe('colorUtils', () => {
  describe('getColorClass white-box', () => {
    test('returns an empty class for invalid input', () => {
      expect(getColorClass()).toBe('')
      expect(getColorClass(null)).toBe('')
      expect(getColorClass(42)).toBe('')
    })

    test('maps each supported branch explicitly', () => {
      expect(getColorClass(' red ')).toBe('color--red')
      expect(getColorClass('BLUE')).toBe('color--blue')
      expect(getColorClass('green')).toBe('color--green')
      expect(getColorClass('#aabbcc')).toBe('color--custom')
      expect(getColorClass('violet')).toBe('color--default')
    })
  })

  describe('getColorClass black-box', () => {
    test.each([
      ['red', 'color--red'],
      ['blue', 'color--blue'],
      ['green', 'color--green'],
      ['#123456', 'color--custom'],
      ['unknown', 'color--default'],
    ])('resolves %s to %s', (input, expected) => {
      expect(getColorClass(input)).toBe(expected)
    })
  })

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
})
