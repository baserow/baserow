import {
  GuidedTourType,
  GuidedTourStep,
} from '@baserow/modules/core/guidedTourTypes'
import Vue from 'vue'

class TablesGuidedTourStep extends GuidedTourStep {
  get title() {
    return 'Setup tables'
  }

  get content() {
    return `Tables store your information neatly. Create a new table within your database to start structuring your data.`
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
    return 'Find Data Fast'
  }

  get content() {
    return `Quickly locate information by filtering and sorting your records.`
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
    return 'Organize Your Data'
  }

  get content() {
    return `Instantly group your records by category, date, or status to clearly visualize patterns and simplify your workflows.`
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
    return 'Customize Your Data'
  }

  get content() {
    return `Click “+” to add new fields (columns). Choose from various field types to capture exactly what matters most to your project.`
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
    return 'Personalize Your Views'
  }

  get content() {
    return `Create custom views like grid, calendar, kanban, or gallery to visualize your data exactly how you want it.`
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
    return 'Create a Form'
  }

  get content() {
    return `Quickly build forms from your tables to collect responses directly into your database, streamlining data collection.`
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

  get welcomeTitle() {
    return ''
  }

  get welcomeContent() {
    return ''
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

  isActive(route) {
    return route.name === 'database-table'
  }
}
