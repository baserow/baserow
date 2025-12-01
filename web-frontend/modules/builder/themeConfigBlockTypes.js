import { Registerable } from '@baserow/modules/core/registry'
import ColorThemeConfigBlock from '@baserow/modules/builder/components/theme/ColorThemeConfigBlock'
import TypographyThemeConfigBlock from '@baserow/modules/builder/components/theme/TypographyThemeConfigBlock'
import ButtonThemeConfigBlock from '@baserow/modules/builder/components/theme/ButtonThemeConfigBlock'
import LinkThemeConfigBlock from '@baserow/modules/builder/components/theme/LinkThemeConfigBlock'
import ImageThemeConfigBlock from '@baserow/modules/builder/components/theme/ImageThemeConfigBlock'
import PageThemeConfigBlock from '@baserow/modules/builder/components/theme/PageThemeConfigBlock'
import InputThemeConfigBlock from '@baserow/modules/builder/components/theme/InputThemeConfigBlock'
import TableThemeConfigBlock from '@baserow/modules/builder/components/theme/TableThemeConfigBlock'
import { FONT_WEIGHTS } from '@baserow/modules/builder/fontWeights'
import {
  resolveColor,
  colorRecommendation,
  colorContrast,
} from '@baserow/modules/core/utils/colors'
import {
  WIDTHS_NEW,
  HORIZONTAL_ALIGNMENTS,
  BACKGROUND_MODES,
} from '@baserow/modules/builder/enums'
import get from 'lodash/get'

/**
 * Helper class to construct easily style objects.
 */
export class ThemeStyle {
  constructor({ colorVariables = {}, $registry }) {
    this.style = {}
    this.colorVariables = colorVariables
    this.$registry = $registry
  }

  addIfExists(theme, propName, styleName, transform = (v) => v) {
    if (!styleName) {
      styleName = `--${propName.replace(/_/g, '-')}`
    }
    if (Object.prototype.hasOwnProperty.call(theme, propName)) {
      this.style[styleName] = transform(theme[propName])
    }
  }

  addColorIfExists(theme, propName, styleName) {
    return this.addIfExists(theme, propName, styleName, (v) =>
      resolveColor(v, this.colorVariables)
    )
  }

  addColorRecommendationIfExists(theme, propName, styleName) {
    return this.addIfExists(theme, propName, styleName, (v) =>
      colorRecommendation(resolveColor(v, this.colorVariables))
    )
  }

  addColorContrastIfExists(theme, propName, styleName) {
    return this.addIfExists(theme, propName, styleName, (v) =>
      colorContrast(resolveColor(v, this.colorVariables))
    )
  }

  addFontFamilyIfExists(theme, propName, styleName) {
    return this.addIfExists(theme, propName, styleName, (v) => {
      const fontFamilyType = this.$registry.get('fontFamily', v)
      return `"${fontFamilyType.name}","${fontFamilyType.safeFont}"`
    })
  }

  addFontWeightIfExists(theme, propName, styleName) {
    return this.addIfExists(theme, propName, styleName, (v) => {
      return FONT_WEIGHTS[v]
    })
  }

  addPixelValueIfExists(theme, propName, styleName) {
    return this.addIfExists(
      theme,
      propName,
      styleName,
      (v) => `${Math.min(100, v)}px`
    )
  }

  toObject() {
    return this.style
  }
}

export class ThemeConfigBlockType extends Registerable {
  get label() {
    return null
  }

  /**
   * Return the CSS to apply for the theme config block. Essentially it's mainly
   * definitions of a bunch of CSS vars that are used by the ABComponents to style
   * themselves.
   *
   * @param {Object} theme the theme to use to populate the CSS vars.
   * @param {Array} colorVariables the color variable mapping.
   * @returns an object that can be use as style property for a DOM element
   */
  getCSS(theme, colorVariables, baseTheme = null) {
    return null
  }

  /**
   * Returns the color variables provided by this theme config block. These variables
   * can then be used by other theme block properties.
   *
   * @param {Object} theme the theme object that contains the value definitions.
   * @returns An array of color variables.
   */
  getColorVariables(theme) {
    return []
  }

  /**
   * Returns the component to configure this theme block.
   */
  get component() {
    return null
  }

  /**
   * Iterate over the registered theme blocks to generate the full CSS style object.
   * This object can then be used to style the application.
   *
   * @param {Array} themeBlocks the list of themeBlocks to consider.
   * @param {Object} theme the theme of the application.
   * @param {Array} colorVariables the color variables array.
   * @returns
   */
  static getAllStyles(
    themeBlocks,
    theme,
    colorVariables = null,
    baseTheme = null
  ) {
    if (colorVariables === null) {
      colorVariables = this.getAllColorVariables(themeBlocks, theme)
    }
    return (
      themeBlocks
        .map((block) => block.getCSS(theme, colorVariables, baseTheme))
        // Flatten the array of objects
        .reduce((acc, obj) => ({ ...acc, ...obj }), {})
    )
  }

  /**
   * Get all variables from all theme blocks.
   *
   * @param {Array} themeBlocks theme blocks to consider
   * @param {Object} theme theme of the application
   * @returns the color variables array
   */
  static getAllColorVariables(themeBlocks, theme) {
    return themeBlocks.map((block) => block.getColorVariables(theme)).flat()
  }

  getOrder() {
    return 50
  }
}

export class ColorThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'color'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.color')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addIfExists(theme, 'primary_color', '--main-primary-color', (v) =>
      resolveColor(v, colorVariables)
    )
    style.addIfExists(theme, 'secondary_color', '--main-secondary-color', (v) =>
      resolveColor(v, colorVariables)
    )
    style.addIfExists(theme, 'border_color', '--main-border-color', (v) =>
      resolveColor(v, colorVariables)
    )
    style.addIfExists(
      theme,
      'main_success_color',
      '--main-success-color',
      (v) => resolveColor(v, colorVariables)
    )
    style.addIfExists(
      theme,
      'main_warning_color',
      '--main-warning-color',
      (v) => resolveColor(v, colorVariables)
    )
    style.addIfExists(theme, 'main_error_color', '--main-error-color', (v) =>
      resolveColor(v, colorVariables)
    )
    return style.toObject()
  }

  getColorVariables(theme) {
    const { i18n } = this.app
    const customColors = theme.custom_colors ? [...theme.custom_colors] : []
    return [
      {
        name: i18n.t('colorThemeConfigBlockType.transparent'),
        value: 'transparent',
        color: '#00000000',
      },
      {
        name: i18n.t('colorThemeConfigBlockType.primary'),
        value: 'primary',
        color: theme.primary_color,
      },
      {
        name: i18n.t('colorThemeConfigBlockType.secondary'),
        value: 'secondary',
        color: theme.secondary_color,
      },
      {
        name: i18n.t('colorThemeConfigBlockType.border'),
        value: 'border',
        color: theme.border_color,
      },
      {
        name: i18n.t('colorThemeConfigBlockType.success'),
        value: 'success',
        color: theme.main_success_color,
      },
      {
        name: i18n.t('colorThemeConfigBlockType.warning'),
        value: 'warning',
        color: theme.main_warning_color,
      },
      {
        name: i18n.t('colorThemeConfigBlockType.error'),
        value: 'error',
        color: theme.main_error_color,
      },
      ...customColors,
    ]
  }

  get component() {
    return ColorThemeConfigBlock
  }

  getOrder() {
    return 10
  }
}

export class TypographyThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'typography'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.typography')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    Array.from([1, 2, 3, 4, 5, 6]).forEach((level) => {
      style.addPixelValueIfExists(
        theme,
        `heading_${level}_font_size`,
        `--heading-h${level}-font-size`
      )
      style.addColorIfExists(
        theme,
        `heading_${level}_text_color`,
        `--heading-h${level}-color`,
        (v) => resolveColor(v, colorVariables)
      )

      style.addIfExists(
        theme,
        `heading_${level}_text_alignment`,
        `--heading-h${level}-text-alignment`
      )
      style.addFontFamilyIfExists(
        theme,
        `heading_${level}_font_family`,
        `--heading-h${level}-font-family`
      )
      style.addFontWeightIfExists(
        theme,
        `heading_${level}_font_weight`,
        `--heading-h${level}-font-weight`
      )
      style.addIfExists(
        theme,
        `heading_${level}_text_decoration`,
        `--heading-h${level}-text-decoration`,
        (v) => {
          const value = []
          if (v[0]) {
            value.push('underline')
          }
          if (v[1]) {
            value.push('line-through')
          }
          if (value.length === 0) {
            return 'none'
          }
          return value.join(' ')
        }
      )
      style.addIfExists(
        theme,
        `heading_${level}_text_decoration`,
        `--heading-h${level}-text-transform`,
        (v) => (v[2] ? 'uppercase' : 'none')
      )
      style.addIfExists(
        theme,
        `heading_${level}_text_decoration`,
        `--heading-h${level}-font-style`,
        (v) => (v[3] ? 'italic' : 'none')
      )
    })
    style.addPixelValueIfExists(theme, `body_font_size`)
    style.addColorIfExists(theme, `body_text_color`)
    style.addColorRecommendationIfExists(
      theme,
      'body_text_color',
      '--body-text-color-complement'
    )
    style.addIfExists(theme, `body_text_alignment`)
    style.addFontFamilyIfExists(theme, `body_font_family`)
    style.addFontWeightIfExists(theme, `body_font_weight`)

    return style.toObject()
  }

  get component() {
    return TypographyThemeConfigBlock
  }

  getOrder() {
    return 20
  }
}

export class ButtonThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'button'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.button')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addColorIfExists(theme, 'button_background_color')
    style.addColorIfExists(theme, 'button_hover_background_color')
    style.addColorIfExists(theme, 'button_text_color')
    style.addColorIfExists(theme, 'button_hover_text_color')
    style.addColorIfExists(theme, 'button_border_color')
    style.addColorIfExists(theme, 'button_hover_border_color')
    style.addColorIfExists(theme, 'button_active_background_color')
    style.addColorIfExists(theme, 'button_active_text_color')
    style.addColorIfExists(theme, 'button_active_border_color')

    style.addIfExists(theme, 'button_width', null, (v) =>
      v === WIDTHS_NEW.FULL ? '100%' : 'auto'
    )
    style.addIfExists(theme, 'button_text_alignment')
    style.addIfExists(
      theme,
      'button_alignment',
      null,
      (v) =>
        ({
          [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
          [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
          [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
        }[v])
    )
    style.addFontFamilyIfExists(theme, `button_font_family`)
    style.addFontWeightIfExists(theme, `button_font_weight`)
    style.addPixelValueIfExists(theme, `button_font_size`)
    style.addPixelValueIfExists(theme, `button_border_radius`)
    style.addPixelValueIfExists(theme, `button_border_size`)
    style.addPixelValueIfExists(theme, `button_horizontal_padding`)
    style.addPixelValueIfExists(theme, `button_vertical_padding`)
    return style.toObject()
  }

  get component() {
    return ButtonThemeConfigBlock
  }

  getOrder() {
    return 40
  }
}

export class LinkThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'link'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.link')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addColorIfExists(theme, 'link_text_color')
    style.addColorIfExists(theme, 'link_hover_text_color')
    style.addColorIfExists(theme, 'link_active_text_color')
    style.addIfExists(
      theme,
      'link_text_alignment',
      '--link-text-alignment',
      (v) =>
        ({
          [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
          [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
          [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
        }[v])
    )
    style.addIfExists(theme, `link_font_family`, `--link-font-family`, (v) => {
      const fontFamilyType = this.app.$registry.get('fontFamily', v)
      return `"${fontFamilyType.name}","${fontFamilyType.safeFont}"`
    })
    style.addIfExists(
      theme,
      'link_default_text_decoration',
      '--link-default-text-decoration',
      (v) => {
        const value = []
        if (v[0]) {
          value.push('underline')
        }
        if (v[1]) {
          value.push('line-through')
        }
        if (value.length === 0) {
          return 'none'
        }
        return value.join(' ')
      }
    )
    style.addIfExists(
      theme,
      'link_default_text_decoration',
      '--link-default-text-transform',
      (v) => (v[2] ? 'uppercase' : 'none')
    )
    style.addIfExists(
      theme,
      'link_default_text_decoration',
      '--link-default-font-style',
      (v) => (v[3] ? 'italic' : 'none')
    )
    style.addIfExists(
      theme,
      'link_hover_text_decoration',
      '--link-hover-text-decoration',
      (v) => {
        const value = []
        if (v[0]) {
          value.push('underline')
        }
        if (v[1]) {
          value.push('line-through')
        }
        if (value.length === 0) {
          return 'none'
        }
        return value.join(' ')
      }
    )
    style.addIfExists(
      theme,
      'link_hover_text_decoration',
      '--link-hover-text-transform',
      (v) => (v[2] ? 'uppercase' : 'none')
    )
    style.addIfExists(
      theme,
      'link_hover_text_decoration',
      '--link-hover-font-style',
      (v) => (v[3] ? 'italic' : 'none')
    )
    style.addIfExists(
      theme,
      'link_active_text_decoration',
      '--link-active-text-decoration',
      (v) => {
        const value = []
        if (v[0]) {
          value.push('underline')
        }
        if (v[1]) {
          value.push('line-through')
        }
        if (value.length === 0) {
          return 'none'
        }
        return value.join(' ')
      }
    )
    style.addIfExists(
      theme,
      'link_active_text_decoration',
      '--link-active-text-transform',
      (v) => (v[2] ? 'uppercase' : 'none')
    )
    style.addIfExists(
      theme,
      'link_active_text_decoration',
      '--link-active-font-style',
      (v) => (v[3] ? 'italic' : 'none')
    )
    style.addPixelValueIfExists(theme, `link_font_size`)
    style.addFontWeightIfExists(theme, `link_font_weight`)
    return style.toObject()
  }

  get component() {
    return LinkThemeConfigBlock
  }

  getOrder() {
    return 50
  }
}

export class ImageThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'image'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.image')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addIfExists(
      theme,
      'image_alignment',
      '--image-alignment',
      (v) =>
        ({
          [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
          [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
          [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
        }[v])
    )

    const imageMaxWidth = get(
      theme,
      'image_max_width',
      baseTheme?.image_max_width
    )
    const imageMaxHeight = get(
      theme,
      'image_max_height',
      baseTheme?.image_max_height
    )
    const imageConstraint = get(
      theme,
      'image_constraint',
      baseTheme?.image_constraint
    )
    const imageBorderRadius = get(
      theme,
      'image_border_radius',
      baseTheme?.image_border_radius
    )

    if (Object.prototype.hasOwnProperty.call(theme, 'image_max_width')) {
      style.style['--image-wrapper-width'] = `${imageMaxWidth}%`
      style.style['--image-wrapper-max-width'] = `${imageMaxWidth}%`
    }

    if (Object.prototype.hasOwnProperty.call(theme, 'image_max_height')) {
      if (imageMaxHeight) {
        style.style['--image-max-width'] = 'auto'
        style.style['--image-wrapper-max-height'] = `${imageMaxHeight}px`
      } else if (baseTheme?.image_max_height) {
        style.style['--image-wrapper-max-height'] = 'none'
      }
    }

    if (Object.prototype.hasOwnProperty.call(theme, 'image_constraint')) {
      switch (imageConstraint) {
        case 'cover':
          style.style['--image-wrapper-width'] = '100%'
          style.style['--image-object-fit'] = 'cover'
          style.style['--image-width'] = '100%'
          style.style['--image-height'] = '100%'
          break
        case 'contain':
          style.style['--image-object-fit'] = 'contain'
          style.style['--image-max-width'] = '100%'
          break
        case 'full-width':
          style.style['--image-object-fit'] = 'fill'
          style.style['--image-width'] = '100%'
          style.style['--image-height'] = '100%'
          style.style['--image-max-width'] = 'none'
          break
      }
    }

    if (Object.prototype.hasOwnProperty.call(theme, 'image_border_radius')) {
      if (imageBorderRadius) {
        style.style['--image-border-radius'] = `${imageBorderRadius}px`
      }
    }

    return style.toObject()
  }

  get component() {
    return ImageThemeConfigBlock
  }

  getOrder() {
    return 60
  }
}

export class PageThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'page'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.page')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addColorIfExists(theme, 'page_background_color')
    style.addColorRecommendationIfExists(
      theme,
      'page_background_color',
      '--page-background-color-complement'
    )
    style.addColorContrastIfExists(
      theme,
      'page_background_color',
      '--page-background-color-contrast'
    )
    style.addIfExists(
      theme,
      'page_background_file',
      '--page-background-image',
      (v) => (v ? `url(${v.url})` : 'none')
    )
    if (theme.page_background_mode === BACKGROUND_MODES.FILL) {
      style.style['--page-background-size'] = 'cover'
      style.style['--page-background-repeat'] = 'no-repeat'
    }
    if (theme.page_background_mode === BACKGROUND_MODES.TILE) {
      style.style['--page-background-size'] = 'auto'
      style.style['--page-background-repeat'] = 'repeat'
    }
    if (theme.page_background_mode === BACKGROUND_MODES.FIT) {
      style.style['--page-background-size'] = 'contain'
      style.style['--page-background-repeat'] = 'no-repeat'
    }
    return style.toObject()
  }

  get component() {
    return PageThemeConfigBlock
  }

  getOrder() {
    return 15
  }
}

export class InputThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'input'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.input')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })

    style.addColorIfExists(theme, 'label_text_color')
    style.addFontFamilyIfExists(theme, `label_font_family`)
    style.addPixelValueIfExists(theme, `label_font_size`)
    style.addFontWeightIfExists(theme, `label_font_weight`)

    style.addColorIfExists(theme, 'input_text_color')
    style.addColorRecommendationIfExists(
      theme,
      'input_text_color',
      '--input-text-color-complement'
    )
    style.addFontFamilyIfExists(theme, `input_font_family`)
    style.addPixelValueIfExists(theme, `input_font_size`)
    style.addFontWeightIfExists(theme, `input_font_weight`)
    style.addColorIfExists(theme, 'input_background_color')
    style.addColorRecommendationIfExists(
      theme,
      'input_background_color',
      '--input-background-color-complement'
    )
    style.addColorIfExists(theme, 'input_border_color')
    style.addColorRecommendationIfExists(
      theme,
      'input_border_color',
      '--input-border-color-complement'
    )
    style.addPixelValueIfExists(theme, `input_border_radius`)
    style.addPixelValueIfExists(theme, `input_border_size`)
    style.addPixelValueIfExists(theme, `input_horizontal_padding`)
    style.addPixelValueIfExists(theme, `input_vertical_padding`)

    return style.toObject()
  }

  get component() {
    return InputThemeConfigBlock
  }

  getOrder() {
    return 55
  }
}

export class TableThemeConfigBlockType extends ThemeConfigBlockType {
  static getType() {
    return 'table'
  }

  get label() {
    return this.app.i18n.t('themeConfigBlockType.table')
  }

  getCSS(theme, colorVariables, baseTheme = null) {
    const style = new ThemeStyle({
      colorVariables,
      $registry: this.app.$registry,
    })
    style.addColorIfExists(theme, 'table_border_color')
    style.addPixelValueIfExists(theme, `table_border_size`)
    style.addPixelValueIfExists(theme, `table_border_radius`)

    style.addColorIfExists(theme, 'table_header_background_color')
    style.addColorIfExists(theme, 'table_header_text_color')
    style.addPixelValueIfExists(theme, `table_header_font_size`)
    style.addFontWeightIfExists(theme, `table_header_font_weight`)
    style.addFontFamilyIfExists(theme, `table_header_font_family`)
    style.addIfExists(theme, `table_header_text_alignment`)

    style.addColorIfExists(theme, 'table_cell_background_color')

    if (
      Object.prototype.hasOwnProperty.call(
        theme,
        'table_cell_alternate_background_color'
      ) &&
      theme.table_cell_alternate_background_color !== 'transparent'
    ) {
      // We want to set the alternate color only if defined
      style.addColorIfExists(theme, 'table_cell_alternate_background_color')
    }
    style.addColorIfExists(theme, 'table_cell_text_color')
    style.addFontFamilyIfExists(theme, `table_cell_font_family`)
    style.addPixelValueIfExists(theme, `table_cell_font_size`)
    style.addIfExists(
      theme,
      'table_cell_alignment',
      null,
      (v) =>
        ({
          [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
          [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
          [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
        }[v])
    )
    style.addPixelValueIfExists(theme, `table_cell_vertical_padding`)
    style.addPixelValueIfExists(theme, `table_cell_horizontal_padding`)

    style.addColorIfExists(theme, 'table_vertical_separator_color')
    style.addPixelValueIfExists(theme, `table_vertical_separator_size`)
    style.addColorIfExists(theme, 'table_horizontal_separator_color')
    style.addPixelValueIfExists(theme, `table_horizontal_separator_size`)

    return style.toObject()
  }

  get component() {
    return TableThemeConfigBlock
  }

  getOrder() {
    return 65
  }
}
