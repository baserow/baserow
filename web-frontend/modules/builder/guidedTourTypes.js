import {
  GuidedTourType,
  GuidedTourStep,
} from '@baserow/modules/core/guidedTourTypes'

class ElementsGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('elementsGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('elementsGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="builder-elements"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class DataGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('dataGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('dataGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="builder-data_sources"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class PreviewGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('previewGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('previewGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="builder-preview"]']
  }

  get position() {
    return 'right-top'
  }
}

class DevicesGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('devicesGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('devicesGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="builder-devices"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class SidePanelPublishGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('sidePanelGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('sidePanelGuidedTourStep.content')
  }

  get selectors() {
    return [
      '[data-highlight="builder-panel-general"]',
      '[data-highlight="builder-panel-style"]',
      '[data-highlight="builder-panel-visibility"]',
      '[data-highlight="builder-panel-events"]',
    ]
  }

  get position() {
    return 'left-top'
  }
}

class PreviewPublishGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('previewPublishGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('previewPublishGuidedTourStep.content')
  }

  get selectors() {
    return [
      '[data-highlight="builder-page-action-preview"]',
      '[data-highlight="builder-page-action-publish"]',
    ]
  }

  get position() {
    return 'left-top'
  }
}

export class BuilderGuidedTourType extends GuidedTourType {
  static getType() {
    return 'builder'
  }

  get steps() {
    return [
      new ElementsGuidedTourStep(this.app),
      new DataGuidedTourStep(this.app),
      new PreviewGuidedTourStep(this.app),
      new DevicesGuidedTourStep(this.app),
      new SidePanelPublishGuidedTourStep(this.app),
      new PreviewPublishGuidedTourStep(this.app),
    ]
  }

  get order() {
    return 300
  }

  isActive() {
    return (
      // Use the `routeMounted` because that gives us the route that's actually
      // mounted, making sure that the selector elements have been rendered.
      this.app.store.getters['routeMounted/routeMounted']?.name ===
      'builder-page'
    )
  }
}
