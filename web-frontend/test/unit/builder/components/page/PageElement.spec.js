import { describe, expect, test, vi } from 'vitest'

import PageElement from '@baserow/modules/builder/components/page/PageElement'
import { BACKGROUND_TYPES } from '@baserow/modules/builder/enums'

describe('PageElement', () => {
  const getElementStyles = (styleBackground, styleBackgroundColor = null) => {
    const context = {
      element: {
        style_background: styleBackground,
        style_background_color: styleBackgroundColor,
        style_background_file: null,
      },
      colorVariables: {},
      border: vi.fn(() => 'none'),
      resolveColor: vi.fn(() => '#123456'),
    }

    return {
      context,
      styles: PageElement.computed.elementStyles.call(context),
    }
  }

  test('uses transparent as the background color when none is configured', () => {
    const { context, styles } = getElementStyles(BACKGROUND_TYPES.NONE)

    expect(styles['--element-background-color']).toBe('transparent')
    expect(context.resolveColor).not.toHaveBeenCalled()
  })

  test('uses the resolved configured background color', () => {
    const { context, styles } = getElementStyles(
      BACKGROUND_TYPES.COLOR,
      'primary'
    )

    expect(styles['--element-background-color']).toBe('#123456')
    expect(context.resolveColor).toHaveBeenCalledWith('primary', {})
  })
})
