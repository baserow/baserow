import {
  GuidedTourStep,
  GuidedTourType,
} from '@baserow/modules/core/guidedTourTypes'

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
}

class TriggerGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('triggerGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('triggerGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-trigger"]']
  }

  get position() {
    return 'bottom-center'
  }
}

class ActionGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('actionGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('actionGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-add-node-btn"]']
  }

  get position() {
    return 'bottom-center'
  }
}

class NodeSidepanelGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('nodeSidepanelGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('nodeSidepanelGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-node-sidepanel"]']
  }

  get position() {
    return 'left-top'
  }
}

class HistoryGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('historyGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('historyGuidedTourStep.content')
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
    return this.app.i18n.t('testRunGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('testRunGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-test-run"]']
  }

  get position() {
    return 'bottom-right'
  }
}

class PublishGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('publishGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('publishGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="automation-publish"]']
  }

  get position() {
    return 'bottom-right'
  }
}

class StateGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('workflowStateGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('workflowStateGuidedTourStep.content')
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
    return this.app.i18n.t('docsGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('docsGuidedTourStep.content')
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
      new TriggerGuidedTourStep(this.app),
      new ActionGuidedTourStep(this.app),
      new NodeSidepanelGuidedTourStep(this.app),
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
      this.app.store.getters['routeMounted/routeMounted']?.name ===
      'automation-workflow'
    )
  }
}
