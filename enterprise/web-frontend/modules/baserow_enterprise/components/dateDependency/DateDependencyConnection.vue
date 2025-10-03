<template>
  <div class="date-dependency__timeline-container">
    <svg :width="width" :height="height" style="pointer-events: none">
      <g
        v-for="(connection, index) in connections"
        :key="`row-connection-${index}`"
        :class="{
          'date-dependency__connection-group--invalid':
            !connection.connection.isValid,
        }"
        style="pointer-events: all"
        class="date-dependency__connection-group"
      >
        <path
          class="date-dependency__path"
          :d="connection.connection.path"
          @pointerenter="onPathPointerEnter(connection, $event)"
          @pointerleave="onPathPointerLeave(connection, $event)"
          @dblclick="onConnectionRemove(connection, $event)"
        />

        <path
          v-if="connection.connection.showRemovePath"
          class="date-dependency__remove-connection"
          :d="connection.connection.removePath"
          @click="onConnectionRemove(connection, $event)"
        />

        <text
          v-if="
            connection.connection.message && connection.connection.showMessage
          "
          class="control__label--small"
          :x="connection.connection.anchorPoint.x"
          :y="connection.connection.anchorPoint.y"
        >
          {{ connection.connection.message }}
        </text>

        <circle
          class="date-dependency__circle date-dependency__circle--start"
          :cx="connection.connection.startPoint.x"
          :cy="connection.connection.startPoint.y"
        />
        <circle
          class="date-dependency__circle date-dependency__circle--end"
          :cx="connection.connection.endPoint.x"
          :cy="connection.connection.endPoint.y"
        />
      </g>
    </svg>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import _ from 'lodash'
import Vue from 'vue'

// milliseconds for a full day
const FULL_DAY = 86400
// pixels to offset a handler for a row
const HANDLER_POINT_OFFSET = 16
// round corner radius in px
const ROUND_RADIUS = 10

// arrow size
const ARROW_HEIGHT = 8
const ARROW_WIDTH = 5

// a minor adjustment for y coordinate to cover padding/margin of an element
const ADJUST_FOR_PADDING = 3

/**
 * Helper class to handle point data and drawing operations in svg.
 */
class Point {
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
class DateDependencyRow {
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

  isValid() {
    const startDate = this.startDate
    const endDate = this.endDate

    return (
      !!startDate &&
      !!endDate &&
      _.isInteger(this.duration) &&
      this.duration >= FULL_DAY &&
      startDate < endDate &&
      // date diff is in milliseconds, so we convert it to seconds
      (endDate - startDate) / 1000 === this.duration - FULL_DAY
    )
  }
}

export default {
  props: {
    rows: { type: Array, required: true },
    fields: { type: Array, required: true },
    rule: { type: Object, required: true },
    width: { type: Number, required: true },
    height: { type: Number, required: true },
    view: { type: Object, required: true },
    storePrefix: { type: String, required: true },
  },
  data() {
    return { drawConnection: null }
  },
  computed: {
    connections() {
      const connections = this.getConnections()
      return connections
    },
  },
  methods: {
    getRowPosition(row) {
      const getPosition = this.$parent.$parent.getRowStyleProps
      const rowHeight = this.$parent.$parent.rowHeight
      const pos = getPosition(row.item)

      const position = {
        left: pos.leftPadding + pos.left,
        top: row.position.top,
        width: pos.width,
        height: rowHeight,
      }
      return position
    },

    getRowFromBuffer(rowId) {
      return this.rows.filter((row) => {
        return row.item !== undefined && row.item.id === rowId
      })[0]
    },

    /**
     * Returns a list of connections between rows
     * @returns {*[]}
     */
    getConnections() {
      const rule = this.rule
      const out = []

      for (const rowItem of this.rows) {
        if (!rowItem.item) {
          continue
        }
        const row = rowItem.item
        const childRow = new DateDependencyRow(rule, row)
        const predecessors = this.getPredecessors(rule, row)
        if (!!predecessors && predecessors.length > 0) {
          for (const predecessor of predecessors) {
            const connection = this.getConnectionForRows(
              rule,
              childRow,
              predecessor
            )
            if (!!connection && !!connection.connection.path) {
              out.push(connection)
            }
          }
        }
      }
      return out
    },
    /**
     * Returns a connection for two rows.
     *
     * @param rule
     * @param child
     * @param parent
     * @returns {*}
     */
    getConnectionForRows(rule, child, parent) {
      const _parentRow = this.getRowFromBuffer(parent.id)

      if (_parentRow === undefined) {
        return
      }
      const parentRow = new DateDependencyRow(rule, _parentRow.item)

      const parentValid = parentRow.isValid()
      const childValid = child.isValid()
      const connectionValid = this.isConnectionValid(child, parentRow)
      const message = this.getConnectionErrorMessage(child, parentRow)
      const connectionPath = this.getConnectionPath(child, parent)
      const connection = {
        isValid: connectionValid && parentValid && childValid,
        isHighlighted: false,
        message,
        showMessage: true,
        ...connectionPath,
      }
      return Vue.observable({
        child,
        parent: parentRow.row,
        parentRow,
        connection,
      })
    },

    /**
     * Calculates error message for a connection.
     *
     * @param child
     * @param parent
     * @returns {*|string}
     */

    getConnectionErrorMessage(child, parent) {
      if (!child.isValid()) {
        return child.getErrorMessage()
      }
      if (!parent.isValid()) {
        return parent.getErrorMessage()
      }
      if (!this.isConnectionValid(child, parent)) {
        if (!child.isValid()) {
          return 'dateDependency.invalidChildRow'
        }
        if (!parent.isValid()) {
          return 'dateDependency.invalidParentRow'
        }
        if (parent.endDate > child.startDate) {
          return 'dateDependency.invalidParentEndDateAfterChildStartDate'
        }
      }
    },

    /**
     * Checks if a connection is valid.
     *
     * @param child
     * @param parent
     * @returns {boolean}
     */
    isConnectionValid(child, parent) {
      return child.startDate > parent.endDate
    },

    /**
     * Returns a connection information: path, start/end points, bouding box, anchor point, remove connection marker.
     *
     * @param child
     * @param parent
     * @returns {{path: *, startPoint: *, endPoint: *, anchorPoint: *, boundingBox: {x, y, width, height}, showRemovePath: boolean, removePath: string}|null}
     */
    getConnectionPath(child, parent) {
      const start = this.getRowFromBuffer(parent.id) // type: referenced row from linkrow
      const end = this.getRowFromBuffer(child.row.id) // type: DependencyRow

      const startPosition = this.getRowPosition(start)
      const endPosition = this.getRowPosition(end)

      if (!endPosition || !startPosition) {
        return null
      }
      const { startPoint, endPoint, anchorPoint, path } =
        this.getConnectionBearingPath(startPosition, endPosition)

      const moveAnchorPoint = _.clone(anchorPoint)
      // drax X
      const removeCommands = [
        moveAnchorPoint.movX(-5).movY(-5).commandMove(),
        moveAnchorPoint.movX(10).movY(10).commandDrawLine(),
        moveAnchorPoint.movX(-10).movY(0).commandMove(),
        moveAnchorPoint.movX(10).movY(-10).commandDrawLine(),
      ]

      // x0, y0, +dx, +dy
      const boundingBox = {
        x: startPoint.x - ROUND_RADIUS,
        y: startPoint.y - ROUND_RADIUS,
        width: endPoint.x - startPoint.x + ROUND_RADIUS * 2,
        height: endPoint.y - startPoint.y + ROUND_RADIUS * 2,
      }

      return {
        path,
        startPoint,
        endPoint,
        anchorPoint,
        boundingBox,
        showRemovePath: true,
        removePath: removeCommands.join(' '),
      }
    },

    /**
     * SE bearing connection
     *
     * [ parent ]
     *        |
     *        +-->[ child ]
     *
     * @param parentPosition
     * @param childPosition
     */
    getConnectionBearingSE(parentPosition, childPosition) {
      const startPoint = new Point(
        parentPosition.left + parentPosition.width - HANDLER_POINT_OFFSET,
        parentPosition.top + parentPosition.height - ADJUST_FOR_PADDING
      )
      const endPoint = new Point(
        childPosition.left,
        childPosition.top + childPosition.height - HANDLER_POINT_OFFSET
      )

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundRightDown())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(-ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndRight())

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },
    /**
     * SE bearing connection
     *         +-->[ child ]
     *        |
     *  [ parent ]
     *
     * @param parentPosition
     * @param childPosition
     */
    getConnectionBearingNE(parentPosition, childPosition) {
      const startPoint = new Point(
        parentPosition.left + parentPosition.width - HANDLER_POINT_OFFSET,
        parentPosition.top + ADJUST_FOR_PADDING
      )
      const endPoint = new Point(
        childPosition.left,
        childPosition.top + childPosition.height - HANDLER_POINT_OFFSET
      )

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundRightUp())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(-ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndRight())

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },

    /**
     * NW bearing connection
     *  [ child ]<--+
     *              |
     *            [ parent ]
     *
     * @param parentPosition
     * @param childPosition
     */
    getConnectionBearingNW(parentPosition, childPosition) {
      const startPoint = new Point(
        parentPosition.left + HANDLER_POINT_OFFSET,
        parentPosition.top + ADJUST_FOR_PADDING
      )
      const endPoint = new Point(
        childPosition.left + childPosition.width - ADJUST_FOR_PADDING * 2,
        childPosition.top + childPosition.height - HANDLER_POINT_OFFSET
      )

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundLeftUp())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(+ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndLeft())

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },

    /**
     * SW bearing connection
     *
     *        [ parent ]
     *               |
     *   [ child ]<--+
     *
     * @param parentPosition
     * @param childPosition
     */
    getConnectionBearingSW(parentPosition, childPosition) {
      const startPoint = new Point(
        parentPosition.left + HANDLER_POINT_OFFSET,
        parentPosition.top + parentPosition.height - ADJUST_FOR_PADDING
      )
      const endPoint = new Point(
        childPosition.left + childPosition.width - ADJUST_FOR_PADDING * 2,
        childPosition.top + childPosition.height - HANDLER_POINT_OFFSET
      )

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundLeftDown())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(+ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndLeft())

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },

    /**
     * Calculates connection path using proper bearing handler.
     *
     * @param parentPosition
     * @param childPosition
     * @returns {*}
     */
    getConnectionBearingPath(parentPosition, childPosition) {
      const bearing = []
      if (childPosition.top > parentPosition.top) {
        bearing.push('S')
      } else {
        bearing.push('N')
      }

      if (childPosition.left > parentPosition.left) {
        bearing.push('E')
      } else {
        bearing.push('W')
      }
      const bearingName = `getConnectionBearing${bearing.join('')}`
      return this[bearingName](parentPosition, childPosition)
    },

    /**
     * Gets a list of predecessors for a row.
     *
     * @param rule
     * @param row
     * @returns {*}
     */
    getPredecessors(rule, row) {
      const depFieldId = rule.dependency_linkrow_field_id
      if (!depFieldId) {
        return
      }
      const fieldName = `field_${depFieldId}`
      const predecessors = row[fieldName]
      return predecessors
    },
    onPathPointerEnter(connection, event) {},
    onPathPointerLeave(connection, event) {},

    /**
     * Removes a connection between rows.
     *
     * @param connection
     * @param event
     * @returns {Promise<void>}
     */
    async onConnectionRemove(connection, event) {
      const parent = connection.parent
      const row = connection.child.row
      const storePrefix = this.storePrefix
      const view = this.view
      const table = this.view.table
      const fields = this.fields
      const rule = this.rule
      const field = fields.filter(
        (_field) => _field.id === rule.dependency_linkrow_field_id
      )[0]

      const fieldName = `field_${field.id}`
      const value = _.clone(row[fieldName])
      const oldValue = _.clone(row[fieldName])

      _.remove(value, (item) => {
        return item.id === parent.id
      })
      const storeName = storePrefix + 'view/timeline/'

      try {
        await this.$store.dispatch(storeName + 'updateRowValue', {
          table,
          view,
          fields,
          row,
          field,
          value,
          oldValue,
        })
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
  },
}
</script>
<style></style>
