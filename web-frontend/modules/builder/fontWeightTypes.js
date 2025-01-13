import { Registerable } from '@baserow/modules/core/registry'

export class FontWeightType extends Registerable {
  get name() {
    return this.app.i18n.t('fontWeightType.regular')
  }

  get weight() {
    return 400
  }
}

export class ThinFontWeightType extends FontWeightType {
  static getType() {
    return 'thin'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.thin')
  }

  get weight() {
    return 100
  }
}

export class UltraLightFontWeightType extends FontWeightType {
  static getType() {
    return 'extra-light'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.extraLight')
  }

  get weight() {
    return 200
  }
}

export class LightFontWeightType extends FontWeightType {
  static getType() {
    return 'light'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.light')
  }

  get weight() {
    return 300
  }
}

export class RegularFontWeightType extends FontWeightType {
  static getType() {
    return 'regular'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.regular')
  }

  get weight() {
    return 400
  }
}

export class MediumFontWeightType extends FontWeightType {
  static getType() {
    return 'medium'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.medium')
  }

  get weight() {
    return 500
  }
}

export class SemiBoldFontWeightType extends FontWeightType {
  static getType() {
    return 'semi-bold'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.semiBold')
  }

  get weight() {
    return 600
  }
}

export class BoldFontWeightType extends FontWeightType {
  static getType() {
    return 'bold'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.bold')
  }

  get weight() {
    return 700
  }
}

export class ExtraBoldFontWeightType extends FontWeightType {
  static getType() {
    return 'extra-bold'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.extraBold')
  }

  get weight() {
    return 800
  }
}

export class BlackFontWeightType extends FontWeightType {
  static getType() {
    return 'black'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.black')
  }

  get weight() {
    return 900
  }
}

export class ExtraBlackFontWeightType extends FontWeightType {
  static getType() {
    return 'extra-black'
  }

  get name() {
    return this.app.i18n.t('fontWeightType.extraBlack')
  }

  get weight() {
    return 950
  }
}
