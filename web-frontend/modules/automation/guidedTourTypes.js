import {
  GuidedTourStep,
  GuidedTourType,
} from '@baserow/modules/core/guidedTourTypes'

class WelcomeGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationWelcomeGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationWelcomeGuidedTourStep.content')
  }

  get selectors() {
    return []
  }

  get position() {
    return 'center'
  }

  get videos() {
    return ['lHfMax7BC5E']
  }
}

class GraphGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationGraphGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationGraphGuidedTourStep.content')
  }

  get selectors() {
    return ['.workflow-editor']
  }

  get position() {
    return 'center'
  }

  get highlightPadding() {
    return 0
  }

  get videos() {
    return ['vaAXEfx-n5U', 'tqa6_5BrVvY', 'p5DwN1CSVPc', 'lbmFNGVIylY']
  }
}

class HistoryGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationHistoryGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationHistoryGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-history"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class TestRunGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationTestRunGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationTestRunGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-test-run"]']
  }

  get position() {
    return 'bottom-right'
  }

  get videos() {
    return ['A06Oeyxx12M']
  }
}

class PublishGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationPublishGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationPublishGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-publish"]']
  }

  get position() {
    return 'bottom-right'
  }

  get videos() {
    return ['A06Oeyxx12M']
  }
}

class StateGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationWorkflowStateGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationWorkflowStateGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-workflow-state"]']
  }

  get position() {
    return 'bottom-center'
  }
}

class DocsGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.$i18n.t('automationDocsGuidedTourStep.title')
  }

  get content() {
    return this.app.$i18n.t('automationDocsGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-docs"]']
  }

  get position() {
    return 'bottom-left'
  }
}

export class AutomationGuidedTourType extends GuidedTourType {
  static getType() {
    return 'automation'
  }

  get steps() {
    return [
      new WelcomeGuidedTourStep(this.app),
      new GraphGuidedTourStep(this.app),
      new HistoryGuidedTourStep(this.app),
      new TestRunGuidedTourStep(this.app),
      new PublishGuidedTourStep(this.app),
      new StateGuidedTourStep(this.app),
      new DocsGuidedTourStep(this.app),
    ]
  }

  get order() {
    return 300
  }

  isActive() {
    return (
      this.app.$store.getters['routeMounted/routeMounted']?.name ===
      'automation-workflow'
    )
  }
}
