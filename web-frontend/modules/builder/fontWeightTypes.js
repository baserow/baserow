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
    100
  }
}

export class UltraLightFontWeightType extends FontWeightType {
  static getType() {
    return 'Ultra-light'
  }

  get name() {
    return 'Extra-light'
  }

  get weight() {
    200
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
    300
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
    400
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
    500
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
    600
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
    700
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
    800
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
    900
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
    950
  }
}
