import {
  ensureString,
  ensureNonEmptyString,
  ensurePositiveInteger,
  ensureArray,
  ensureNumeric,
} from '@baserow/modules/core/utils/validator'
import {
  DataSourceDataProviderType,
  DataSourceContextDataProviderType,
  PageParameterDataProviderType,
  CurrentRecordDataProviderType,
  FormDataProviderType,
  PreviousActionDataProviderType,
  UserDataProviderType,
} from '@baserow/modules/builder/dataProviderTypes'

export const DIRECTIONS = {
  BEFORE: 'before',
  AFTER: 'after',
  LEFT: 'left',
  RIGHT: 'right',
}
export const PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS = {
  numeric: ensurePositiveInteger,
  text: ensureNonEmptyString,
}
export const QUERY_PARAM_TYPE_HANDLER_FUNCTIONS = {
  numeric: (input) => {
    const value = ensureArray(input, { allowEmpty: true }).map((i) =>
      ensureNumeric(i, { allowNull: true })
    )

    return value.length === 0 ? null : value.length === 1 ? value[0] : value
  },
  text: (input) => {
    const value = ensureArray(input, {
      allowEmpty: true,
    }).map((i) => ensureString(i, { allowEmpty: true }))
    return value.length === 0 ? null : value.length === 1 ? value[0] : value
  },
}

export const ALLOWED_LINK_PROTOCOLS = [
  'ftp:',
  'ftps:',
  'ftpes:',
  'http:',
  'https:',
  'mailto:',
  'sftp:',
  'sms:',
  'tel:',
]

export const TEXT_FORMAT_TYPES = {
  PLAIN: 'plain',
  MARKDOWN: 'markdown',
}

export const IMAGE_SOURCE_TYPES = {
  UPLOAD: 'upload',
  URL: 'url',
}

export const IFRAME_SOURCE_TYPES = {
  URL: 'url',
  EMBED: 'embed',
}

export const HORIZONTAL_ALIGNMENTS = {
  LEFT: 'left',
  CENTER: 'center',
  RIGHT: 'right',
}

export const VERTICAL_ALIGNMENTS = {
  TOP: 'top',
  CENTER: 'center',
  BOTTOM: 'bottom',
}

export const WIDTHS = {
  AUTO: { value: 'auto', name: 'widthSelector.widthAuto' },
  FULL: { value: 'full', name: 'widthSelector.widthFull' },
}

export const WIDTHS_NEW = {
  AUTO: 'auto',
  FULL: 'full',
}

export const BACKGROUND_TYPES = {
  NONE: 'none',
  COLOR: 'color',
}

export const BACKGROUND_MODES = {
  FILL: 'fill',
  TILE: 'tile',
  FIT: 'fit',
}

export const PAGE_PLACES = {
  HEADER: 'header',
  CONTENT: 'content',
  FOOTER: 'footer',
}

export const WIDTH_TYPES = {
  SMALL: { value: 'small', name: 'widthTypes.small' },
  MEDIUM: { value: 'medium', name: 'widthTypes.medium' },
  NORMAL: { value: 'normal', name: 'widthTypes.normal' },
  FULL: { value: 'full', name: 'widthTypes.fullBleed' },
  FULL_WIDTH: { value: 'full-width', name: 'widthTypes.fullWidth' },
}

export const CHILD_WIDTH_TYPES = {
  SMALL: { value: 'small', name: 'widthTypes.small' },
  MEDIUM: { value: 'medium', name: 'widthTypes.medium' },
  NORMAL: { value: 'normal', name: 'widthTypes.normal' },
}

export const SHARE_TYPES = {
  ALL: 'all',
  ONLY: 'only',
  EXCEPT: 'except',
}

/**
 * A list of all the data providers that can be used in the formula field on the right
 * sidebar in the application builder.
 *
 * @type {String[]}
 */
export const DATA_PROVIDERS_ALLOWED_ELEMENTS = [
  UserDataProviderType.getType(),
  CurrentRecordDataProviderType.getType(),
  PageParameterDataProviderType.getType(),
  DataSourceDataProviderType.getType(),
  DataSourceContextDataProviderType.getType(),
  FormDataProviderType.getType(),
]

export const DATA_PROVIDERS_ALLOWED_FORM_ELEMENTS = [
  UserDataProviderType.getType(),
  CurrentRecordDataProviderType.getType(),
  PageParameterDataProviderType.getType(),
  DataSourceDataProviderType.getType(),
  DataSourceContextDataProviderType.getType(),
]

/**
 * A list of all the data provider that can be used to configure data sources.
 *
 * @type {String[]}
 */
export const DATA_PROVIDERS_ALLOWED_DATA_SOURCES = [
  UserDataProviderType.getType(),
  PageParameterDataProviderType.getType(),
  DataSourceDataProviderType.getType(),
]

/**
 * A list of all the data providers that can be used to configure workflow actions.
 *
 * @type {String[]}
 */
export const DATA_PROVIDERS_ALLOWED_WORKFLOW_ACTIONS = [
  PreviousActionDataProviderType.getType(),
  ...DATA_PROVIDERS_ALLOWED_ELEMENTS,
]

export const ELEMENT_EVENTS = {
  DATA_SOURCE_REMOVED: 'DATA_SOURCE_REMOVED',
  DATA_SOURCE_AFTER_UPDATE: 'DATA_SOURCE_AFTER_UPDATE',
}

export const ORIENTATIONS = {
  HORIZONTAL: 'horizontal',
  VERTICAL: 'vertical',
}

export const CHOICE_OPTION_TYPES = {
  MANUAL: 'manual',
  DATA_SOURCE: 'data_source',
  FORMULAS: 'formulas',
}

export const LINK_VARIANTS = {
  LINK: 'link',
  BUTTON: 'button',
}

export const DATE_FORMATS = {
  EU: {
    format: 'DD/MM/YYYY',
    name: 'common.dateFormatEU',
    example: '25/04/2024',
  },
  US: {
    format: 'MM/DD/YYYY',
    name: 'common.dateFormatUS',
    example: '04/25/2024',
  },
  ISO: {
    format: 'YYYY-MM-DD',
    name: 'common.dateFormatISO',
    example: '2024-04-25',
  },
}

export const TIME_FORMATS = {
  24: {
    format: 'HH:mm',
    name: 'common.timeFormat24Hour',
    example: '23:00',
  },
  12: {
    format: 'hh:mm A',
    name: 'common.timeFormat12Hour',
    example: '11:00 PM',
  },
}
