import _ from 'lodash'
import { Registerable } from '@baserow/modules/core/registry'
import DateDependencyMenuItem from '@baserow_enterprise/components/dateDependency/DateDependencyMenuItem'
import TimelineFieldRuleType from '@baserow_premium/timelineFieldRuleType'
import DateDependencyConnection from '@baserow_enterprise/components/dateDependency/DateDependencyConnection'

// Date dependency on timeline views
// seconds for a full day
export const FULL_DAY = 86400
// pixels to offset a handler for a row
export const HANDLER_POINT_OFFSET = 16
// round corner radius in px
export const ROUND_RADIUS = 10

// arrow size
export const ARROW_HEIGHT = 8
export const ARROW_WIDTH = 5

// a minor adjustment for y coordinate to cover padding/margin of an element
export const ADJUST_FOR_PADDING = 3
export const ROW_HANDLE_DIRECTIONS = ['NE', 'SE', 'NW', 'SW', 'E', 'W']

export const DependencyLinkRowRoles = {
  PREDECESSORS: 'predecessors',
  SUCCESSORS: 'successors',

  items() {
    return [
      DependencyLinkRowRoles.PREDECESSORS,
      DependencyLinkRowRoles.SUCCESSORS,
    ]
  },

  toLabels() {
    return [{ label: this.PREDECESSORS }, { label: this.SUCCESSORS }]
  },
  getIndex(label) {
    const items = DependencyLinkRowRoles.items()
    const idx = items.indexOf(label)
    return idx > -1 ? idx : 0
  },
}

export const DependencyConnectionTypes = {
  END_TO_START: 'end-to-start',
  END_TO_END: 'end-to-end',
  START_TO_END: 'start-to-end',
  START_TO_START: 'start-to-start',

  toLabels() {
    return [
      { label: this.END_TO_START },
      { label: this.END_TO_END },
      { label: this.START_TO_END },
      { label: this.START_TO_START },
    ]
  },
  toFields() {
    return [
      { name: this.END_TO_START, id: this.END_TO_START, description: '' },
      { name: this.END_TO_END, id: this.END_TO_END, description: '' },
      { name: this.START_TO_END, id: this.START_TO_END, description: '' },
      { name: this.START_TO_START, id: this.START_TO_START, description: '' },
    ]
  },
}

export const DependencyBufferType = {
  FLEXIBLE: 'flexible',
  FIXED: 'fixed',
  NONE: 'none',

  toLabels() {
    return [
      { label: this.FLEXIBLE },
      { label: this.FIXED },
      { label: this.NONE },
    ]
  },
  toFields() {
    return [
      { id: this.FLEXIBLE, name: this.FLEXIBLE, description: '' },
      { id: this.FIXED, name: this.FIXED, description: '' },
      { id: this.NONE, name: this.NONE, description: '' },
    ]
  },
}

export class DateDependencyContextItemType extends Registerable {
  static getType() {
    return 'date_dependency'
  }

  getComponent() {
    return DateDependencyMenuItem
  }
}

export class DateDependencyTimelineComponent extends TimelineFieldRuleType {
  getType() {
    return 'date_dependency'
  }

  getTimelineFieldRuleComponent(rule, view, database) {
    if (
      this.app.$hasPermission(
        'database.table.field_rules.read_field_rules',
        view.table,
        database.workspace.id
      )
    ) {
      return DateDependencyConnection
    }
  }
}

/**
 * Helper class to handle point data and drawing operations in svg.
 */
export class Point {
  constructor(x, y) {
    this.x = x
    this.y = y
  }

  setX(x) {
    this.x = x
    return this
  }

  movX(dx) {
    return this.setX(this.x + dx)
  }

  movY(dy) {
    return this.setY(this.y + dy)
  }

  setY(y) {
    this.y = y
    return this
  }

  get coordX() {
    return this.x.toFixed()
  }

  get coordY() {
    return this.y.toFixed()
  }

  commandDrawLine() {
    return `L ${this.commandPoint()}`
  }

  commandMove() {
    return `M ${this.commandPoint()}`
  }

  commandPoint() {
    return ` ${this.coordX},${this.coordY} `
  }

  commandRoundRightDown(radius = ROUND_RADIUS) {
    const init = _.clone(this)
    this.movX(radius).movY(radius)

    return `C ${init.x} ${init.y + radius},  ${init.x} ${init.y + radius}, ${
      this.coordX
    } ${this.coordY}`
  }

  commandRoundLeftDown(radius = ROUND_RADIUS) {
    const init = _.clone(this)
    this.movX(-radius).movY(radius)

    return `C ${init.x} ${init.y + radius},  ${init.x} ${init.y + radius}, ${
      this.coordX
    } ${this.coordY}`
  }

  commandRoundRightUp(radius = ROUND_RADIUS) {
    const init = _.clone(this)
    this.movX(radius).movY(-radius)

    return `C ${init.x} ${init.y - radius},  ${init.x} ${init.y - radius}, ${
      this.coordX
    } ${this.coordY}`
  }

  commandRoundLeftUp(radius = ROUND_RADIUS) {
    const init = _.clone(this)
    this.movX(-radius).movY(-radius)

    return `C ${init.x} ${init.y - radius},  ${init.x} ${init.y - radius}, ${
      this.coordX
    } ${this.coordY}`
  }

  /**
   * Creates an arrow pointing to the left
   *
   *  /
   *  \
   *
   * @param arrowWidth
   * @param arrowHeight
   * @returns {string}
   */
  commandHorizontalArrowEndLeft(
    arrowWidth = ARROW_WIDTH,
    arrowHeight = ARROW_HEIGHT
  ) {
    const arrow = _.clone(this)
    const commands = []
    arrow.movX(arrowWidth).movY(-arrowHeight / 2)
    commands.push(arrow.commandMove())
    arrow.movX(-arrowWidth).movY(arrowHeight / 2)
    commands.push(arrow.commandDrawLine())
    arrow.movX(arrowWidth).movY(arrowHeight / 2)
    commands.push(arrow.commandDrawLine())

    return commands.join(' ')
  }

  /**
   * Creates an arrow pointing to the right
   *
   *  \
   *  /
   *
   * @param arrowWidth
   * @param arrowHeight
   * @returns {string}
   */
  commandHorizontalArrowEndRight(
    arrowWidth = ARROW_WIDTH,
    arrowHeight = ARROW_HEIGHT
  ) {
    const arrow = _.clone(this)
    const commands = []
    arrow.movX(-arrowWidth).movY(-arrowHeight / 2)
    commands.push(arrow.commandMove())
    arrow.movX(arrowWidth).movY(arrowHeight / 2)
    commands.push(arrow.commandDrawLine())
    arrow.movX(-arrowWidth).movY(arrowHeight / 2)
    commands.push(arrow.commandDrawLine())

    return commands.join(' ')
  }
}

/**
 * Helper class to handle date dependency rows
 */
export class DateDependencyRow {
  constructor(rule, row) {
    this.rule = rule
    this.row = row
  }

  get startDate() {
    return Date.parse(this.getFieldValue('start_date_field_id'))
  }

  get endDate() {
    return Date.parse(this.getFieldValue('end_date_field_id'))
  }

  get duration() {
    return this.getFieldValue('duration_field_id')
  }

  get linkrow() {
    return this.getFieldValue('dependency_linkrow_field_id')
  }

  getFieldValue(ruleFieldName) {
    const fieldName = this.getFieldName(this.rule[ruleFieldName])
    if (fieldName === null) {
      return
    }
    return this.row[fieldName]
  }

  getFieldName(fieldId) {
    return fieldId ? `field_${fieldId}` : null
  }

  getErrorMessage() {
    if (!this.startDate) {
      return 'dateDependency.invalidStartDateEmpty'
    }
    if (!this.endDate) {
      return 'dateDependency.invalidEndDateEmpty'
    }
    if (this.endDate < this.startDate) {
      return 'dateDependency.invalidEndDateBeforeStartDate'
    }
    if (!this.duration) {
      return 'dateDependency.invalidDurationEmpty'
    }
    if (this.duration < FULL_DAY) {
      return 'dateDependency.invalidDurationValue'
    }
    // date diff is in milliseconds, so we convert it to seconds
    if (this.duration !== (this.endDate - this.startDate) / 1000 + FULL_DAY) {
      return 'dateDependency.invalidDurationMismatch'
    }
  }

  isFetching() {
    return this.row._.fetching
  }

  isValid() {
    const startDate = this.startDate
    const endDate = this.endDate

    return (
      _.isInteger(startDate) &&
      _.isInteger(endDate) &&
      _.isInteger(this.duration) &&
      this.duration >= FULL_DAY &&
      startDate < endDate &&
      // date diff is in milliseconds, so we convert it to seconds
      (endDate - startDate) / 1000 === this.duration - FULL_DAY
    )
  }
}
