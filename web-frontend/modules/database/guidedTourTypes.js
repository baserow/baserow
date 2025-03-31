import {
  GuidedTourType,
  GuidedTourStep,
} from '@baserow/modules/core/guidedTourTypes'
import Vue from 'vue'

class TablesGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('tablesGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('tablesGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="create-table"]']
  }

  get position() {
    return 'right-bottom'
  }
}

class FiltersAndSortGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('filtersAndSortGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('filtersAndSortGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="view-filters"]', '[data-highlight="view-sorts"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class GroupByGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('groupByGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('groupByGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="view-group-by"]']
  }

  get position() {
    return 'bottom-right'
  }
}

class AddFieldGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('addFieldGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('addFieldGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="add-field"]']
  }

  get position() {
    return 'bottom-right'
  }
}

class CreateViewGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('createViewGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('createViewGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="views"]']
  }

  get position() {
    return 'bottom-left'
  }
}

class CreateFormViewGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('createFormViewGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('createFormViewGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="create-view-form"]']
  }

  get position() {
    return 'bottom-left'
  }

  async beforeShow() {
    this.app.$bus.$emit('open-table-views')
    await Vue.nextTick()
  }

  afterShow() {
    this.app.$bus.$emit('close-table-views')
  }
}

export class DatabaseGuidedTourType extends GuidedTourType {
  static getType() {
    return 'database'
  }

  get steps() {
    return [
      new TablesGuidedTourStep(this.app),
      new FiltersAndSortGuidedTourStep(this.app),
      new GroupByGuidedTourStep(this.app),
      new AddFieldGuidedTourStep(this.app),
      new CreateViewGuidedTourStep(this.app),
      new CreateFormViewGuidedTourStep(this.app),
    ]
  }

  get order() {
    return 200
  }

  isActive(route) {
    return route.name === 'database-table'
  }
}
