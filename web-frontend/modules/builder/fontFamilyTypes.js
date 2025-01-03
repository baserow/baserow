import { Registerable } from '@baserow/modules/core/registry'

export class FontFamilyType extends Registerable {
  get name() {
    return ''
  }

  get safeFont() {
    return 'sans-serif'
  }

  get weights() {
    return ['regular', 'bold']
  }

  get defaultWeight() {
    return 'regular'
  }
}

export class InterFontFamilyType extends FontFamilyType {
  static getType() {
    return 'inter'
  }

  get name() {
    return 'Inter'
  }

  get weights() {
    return ['regular', 'medium', 'semi-bold', 'bold']
  }
}

export class ArialFontFamilyType extends FontFamilyType {
  static getType() {
    return 'arial'
  }

  get name() {
    return 'Arial'
  }
}

export class VerdanaFontFamilyType extends FontFamilyType {
  static getType() {
    return 'verdana'
  }

  get name() {
    return 'Verdana'
  }
}

export class TahomaFontFamilyType extends FontFamilyType {
  static getType() {
    return 'tahoma'
  }

  get name() {
    return 'Tahoma'
  }
}

export class TrebuchetMSFontFamilyType extends FontFamilyType {
  static getType() {
    return 'trebuchet_ms'
  }

  get name() {
    return 'Trebuchet MS'
  }
}

export class TimesNewRomanFontFamilyType extends FontFamilyType {
  static getType() {
    return 'times_new_roman'
  }

  get name() {
    return 'Times new roman'
  }

  get safeFont() {
    return 'serif'
  }
}

export class GeorgiaFontFamilyType extends FontFamilyType {
  static getType() {
    return 'georgia'
  }

  get name() {
    return 'Georgia'
  }

  get safeFont() {
    return 'serif'
  }
}

export class GaramondFontFamilyType extends FontFamilyType {
  static getType() {
    return 'garamond'
  }

  get name() {
    return 'Garamond'
  }

  get safeFont() {
    return 'serif'
  }
}

export class CourierNewFontFamilyType extends FontFamilyType {
  static getType() {
    return 'courier_new'
  }

  get name() {
    return 'Courier new'
  }

  get safeFont() {
    return 'monospace'
  }
}

export class BrushScriptMTFontFamilyType extends FontFamilyType {
  static getType() {
    return 'brush_script_mt'
  }

  get name() {
    return 'Brush Script MT'
  }

  get safeFont() {
    return 'cursive'
  }

  get weights() {
    return ['regular', 'bold']
  }
}

export class GoogleFontFamilyType extends FontFamilyType {
  constructor({ app, name, type }) {
    super({ app })
    this._name = name
    this._type = type
  }

  getType() {
    return this._type
  }

  get name() {
    return this._name
  }
}

// Example of a google font object:
//
// {
//   "id": "abeezee",
//   "family": "ABeeZee",
//   "subsets": [
//       "latin",
//       "latin-ext"
//   ],
//   "weights": [
//       400
//   ],
//   "styles": [
//       "italic",
//       "normal"
//   ],
//   "defSubset": "latin",
//   "variable": false,
//   "lastModified": "2024-09-04",
//   "category": "sans-serif",
//   "license": "OFL-1.1",
//   "type": "google"
// }