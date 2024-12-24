import { Registerable } from '@baserow/modules/core/registry'

export class FontWeightType extends Registerable {
  get name() {
    return 'Regular'
  }

  get weight() {
    return 400
  }
}

export class ThinFontWeightType extends FontWeightType {
  static getType() {
    return 'Thin'
  }

  get name() {
    return 'Thin'
  }

  get weight() {
    return 100
  }
}

export class UltraLightFontWeightType extends FontWeightType {
  static getType() {
    return 'Extra-light'
  }

  get name() {
    return 'Extra-light'
  }

  get weight() {
    return 200
  }
}

export class LightFontWeightType extends FontWeightType {
  static getType() {
    return 'Light'
  }

  get name() {
    return 'Light'
  }

  get weight() {
    return 300
  }
}

export class RegularFontWeightType extends FontWeightType {
  static getType() {
    return 'Regular'
  }

  get name() {
    return 'Regular'
  }

  get weight() {
    return 400
  }
}

export class MediumFontWeightType extends FontWeightType {
  static getType() {
    return 'Medium'
  }

  get name() {
    return 'Medium'
  }

  get weight() {
    return 500
  }
}

export class SemiBoldFontWeightType extends FontWeightType {
  static getType() {
    return 'Semi-bold'
  }

  get name() {
    return 'Semi-bold'
  }

  get weight() {
    return 600
  }
}

export class BoldFontWeightType extends FontWeightType {
  static getType() {
    return 'Bold'
  }

  get name() {
    return 'Bold'
  }

  get weight() {
    return 700
  }
}

export class ExtraBoldFontWeightType extends FontWeightType {
  static getType() {
    return 'Extra-bold'
  }

  get name() {
    return 'Extra-bold'
  }

  get weight() {
    return 800
  }
}

export class BlackFontWeightType extends FontWeightType {
  static getType() {
    return 'Black'
  }

  get name() {
    return 'Black'
  }

  get weight() {
    return 900
  }
}

export class ExtraBlackFontWeightType extends FontWeightType {
  static getType() {
    return 'Extra-black'
  }

  get name() {
    return 'Extra-black'
  }

  get weight() {
    return 950
  }
}
