import {
  GuidedTourType,
  GuidedTourStep,
} from '@baserow/modules/core/guidedTourTypes'
import Vue from 'vue'
import { GridViewType } from '@baserow/modules/database/viewTypes'

class FiltersSortGroupGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('filterSortGroupGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('filterSortGroupGuidedTourStep.content')
  }

  get selectors() {
    return [
      '[data-highlight="view-filters"]',
      '[data-highlight="view-sorts"]',
      '[data-highlight="view-group-by"]',
    ]
  }

  get position() {
    return 'bottom-left'
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
    this.app.$bus.$emit('open-table-views-context')
    await Vue.nextTick()
  }

  afterShow() {
    this.app.$bus.$emit('close-table-views-context')
  }
}

class ViewOptionGuidedTourStep extends GuidedTourStep {
  get title() {
    return this.app.i18n.t('viewOptionsGuidedTourStep.title')
  }

  get content() {
    return this.app.i18n.t('viewOptionsGuidedTourStep.content')
  }

  get selectors() {
    return ['[data-highlight="view-options"]']
  }

  get position() {
    return 'bottom-left'
  }

  async beforeShow() {
    this.app.$bus.$emit('open-table-view-context')
    await Vue.nextTick()
  }

  afterShow() {
    this.app.$bus.$emit('close-table-view-context')
  }
}

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

export class DatabaseGuidedTourType extends GuidedTourType {
  static getType() {
    return 'database'
  }

  get steps() {
    return [
      new FiltersSortGroupGuidedTourStep(this.app),
      new AddFieldGuidedTourStep(this.app),
      new CreateViewGuidedTourStep(this.app),
      new CreateFormViewGuidedTourStep(this.app),
      new ViewOptionGuidedTourStep(this.app),
      new TablesGuidedTourStep(this.app),
    ]
  }

  get order() {
    return 200
  }

  isActive() {
    return (
      // Use the `routeMounted` because that gives us the route that's actually
      // mounted, making sure that the selector elements have been rendered.
      this.app.store.getters['routeMounted/routeMounted']?.name ===
        'database-table' &&
      // This tour is only compatible with the grid view.
      this.app.store.getters['view/getSelected']?.type ===
        GridViewType.getType()
    )
  }
}
