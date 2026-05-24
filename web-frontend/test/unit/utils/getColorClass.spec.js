import { getColorClass } from '@baserow/modules/core/utils/colors'

describe('getColorClass — Caixa Branca (Branch + MC/DC)', () => {
  // Branch A — entrada inválida (null/undefined/não-string)
  test('[Branch A] null retorna string vazia', () => {
    expect(getColorClass(null)).toBe('')
  })
  test('[Branch A] número retorna string vazia', () => {
    expect(getColorClass(42)).toBe('')
  })

  // Branch B — red
  test('[Branch B] "red" retorna "color--red"', () => {
    expect(getColorClass('red')).toBe('color--red')
  })
  // Branch B com variação — trim + lowercase (cobre .trim().toLowerCase())
  test('[Branch B] " Red " (espaços e maiúsculas) retorna "color--red"', () => {
    expect(getColorClass(' Red ')).toBe('color--red')
  })

  // Branch C — blue
  test('[Branch C] "blue" retorna "color--blue"', () => {
    expect(getColorClass('blue')).toBe('color--blue')
  })
  test('[Branch C] "BLUE" retorna "color--blue"', () => {
    expect(getColorClass('BLUE')).toBe('color--blue')
  })

  // Branch D — green
  test('[Branch D] "green" retorna "color--green"', () => {
    expect(getColorClass('green')).toBe('color--green')
  })
  test('[Branch D] "GREEN" retorna "color--green"', () => {
    expect(getColorClass('GREEN')).toBe('color--green')
  })

  // Branch E — hex color
  test('[Branch E] "#FF0000" retorna "color--custom"', () => {
    expect(getColorClass('#FF0000')).toBe('color--custom')
  })
  test('[Branch E] "#abc" retorna "color--custom"', () => {
    expect(getColorClass('#abc')).toBe('color--custom')
  })

  // Branch F — cor desconhecida
  test('[Branch F] "yellow" retorna "color--default"', () => {
    expect(getColorClass('yellow')).toBe('color--default')
  })
  test('[Branch F] "purple" retorna "color--default"', () => {
    expect(getColorClass('purple')).toBe('color--default')
  })
})
