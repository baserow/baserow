import { Registerable } from '@baserow/modules/core/registry'

export class GuidedTourType extends Registerable {
  get canSkip() {
    return false
  }

  get order() {
    return 100
  }

  /**
   * @TODO docs
   */
  isActive() {
    throw new Error('The GuidedTourType.isActive method must be implemented.')
  }
}

export class GuidedTourStep {
  constructor(
    app,
    title = null,
    content = null,
    selector = null,
    position = 'right-top'
  ) {
    this.app = app
    this._title = title
    this._content = content
    this._selector = selector
    this._position = position
  }

  /**
   * If set, it will be shown as title at the top of the visual step.
   */
  get title() {
    return this._title
  }

  /**
   * Markdown content at the body of the step.
   */
  get content() {
    if (this._content === null) {
      throw new Error('The content must be set in a guided tour step.')
    }
    return this._content
  }

  /**
   * Can contain one or more selectors that must be highlighted. If multiple are
   * provided, the elements must be directly next to each other.
   */
  get selector() {
    return this._selector
  }

  /**
   * Indicates where the step must be displayed. If `POSITION_CENTER`, no elements
   * will be highlighted. Anything else, and the element will be placed related to
   * the selected elements by the selector.
   */
  get position() {
    return this._position
  }

  /**
   * If null is returned, then the default button text will be used.
   */
  get buttonText() {
    return null
  }

  /**
   * @TODO docs
   */
  get skipIfNotFirst() {
    return false
  }

  /**
   * @TODO logs
   */
  beforeShow() {}

  /**
   * @TODO logs
   */
  afterShow() {}
}

class WelcomeGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('welcomeGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('welcomeGuidedTourStep.content')
  }

  get selectors() {
    return []
  }

  get position() {
    return 'center'
  }

  get buttonText() {
    return this.app.i18n.t('welcomeGuidedTourStep.buttonText')
  }

  get skipIfNotFirst() {
    return true
  }
}

class ControlCenterGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('controlCenterGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('controlCenterGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="workspaces"]', '[data-highlight="menu"]']
  }

  get position() {
    return 'right-top'
  }
}

class CreateNewGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('createNewGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('createNewGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="create-new"]']
  }

  get position() {
    return 'right-bottom'
  }
}

export class SidebarGuidedTourType extends GuidedTourType {
  static getType() {
    return 'sidebar'
  }

  get steps() {
    return [
      new WelcomeGuidedTourStep(this.app),
      new ControlCenterGuidedTourStep(this.app),
      new CreateNewGuidedTourStep(this.app),
    ]
  }

  get order() {
    return 100
  }

  isActive() {
    return true
  }
}
