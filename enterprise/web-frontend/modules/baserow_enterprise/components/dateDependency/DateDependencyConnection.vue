<template>
  <div ref="container" class="date-dependency__timeline-container">
    <svg
      :width="width"
      :height="height"
      @mousedown="onDragStart($event)"
      @mousemove="onDragMove($event)"
      @mouseup="onDragEnd($event)"
    >
      <g v-for="dz in dropZones" :key="dz.row.item.id">
        <rect
          :id="`row-${dz.row.item.id}-activator`"
          class="date-dependency__bounding-box-activator"
          :x="dz.position.left - 10"
          :y="dz.position.top - 10"
          :width="dz.position.width + 20"
          :height="dz.position.height + 20"
        />

        <rect
          :id="`row-${dz.row.item.id}-droppable`"
          class="date-dependency__bounding-box"
          :x="dz.position.left"
          :y="dz.position.top"
          :width="dz.position.width"
          :height="dz.position.height"
          :data-row-id="dz.row.item.id"
          rx="5"
          ry="5"
        />
      </g>

      <g v-for="(rowItem, rindex) in rows" :key="`row-${rindex}`">
        <g
          v-for="(connection, cindex) in getConnectionsForRow(rowItem)"
          :key="`row-connection-${cindex}`"
          :class="{
            'date-dependency__connection-group--invalid':
              !connection.connection.isValid,
          }"
          class="date-dependency__connection-group"
        >
          <path
            class="date-dependency__path"
            :d="connection.connection.path"
            @dblclick="onConnectionRemove(connection, $event)"
          />

          <path
            v-if="connection.connection.showRemovePath"
            class="date-dependency__remove-connection"
            :d="connection.connection.removePath"
            @click="onConnectionRemove(connection, $event)"
          />

          <text
            v-if="connection.connection.message"
            class="date-dependency__text"
            :x="connection.connection.anchorPoint.x"
            :y="connection.connection.anchorPoint.y"
          >
            {{ connection.connection.message }}
          </text>

          <circle
            class="date-dependency__circle date-dependency__circle--end"
            :cx="connection.connection.endPoint.x"
            :cy="connection.connection.endPoint.y"
            :data-row-id="connection.child.id"
          />
        </g>
        <circle
          v-for="(handlePoint, hindex) in getHandlePointsForRow(rowItem)"
          :key="`row-handler-${rindex}-${hindex}`"
          :cx="handlePoint.x"
          :cy="handlePoint.y"
          :data-row-id="rowItem.item.id"
          class="date-dependency__circle date-dependency__circle--start"
        />
      </g>

      <circle
        ref="handle"
        class="date-dependency__circle date-dependency__circle--handle"
        :cx="dragPoint.x"
        :cy="dragPoint.y"
      />

      <path class="date-dependency__path--creating" :d="drawConnection" />
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
    return {
      drawConnection: null,
      dragStartPoint: null,
      dragEndPoint: null,
      dragPoint: new Point(0, 0),
    }
  },
  computed: {
    dropZones() {
      const dropZones = []
      this.rows.forEach((row) => {
        if (row.item) {
          const position = this.getRowPosition(row)
          dropZones.push({ row, position })
        }
      })
      return dropZones
    },
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
    getHandlePointsForRow(rowItem) {
      const out = []
      const rowPosition = this.getRowPosition(rowItem)
      if (!rowPosition) {
        return out
      }
      const DIRECTIONS = ['NE', 'SE', 'NW', 'SW', 'E', 'W']
      for (const direction of DIRECTIONS) {
        const callable = this[`getPointBearing${direction}`]
        const point = callable(rowPosition)
        out.push(point)
      }
      return out
    },
    getConnectionsForRow(rowItem) {
      const rule = this.rule
      const out = []

      if (rowItem.item) {
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
     * Returns a list of connections between rows
     * @returns {*[]}
     */
    getConnections() {
      const out = []

      for (const rowItem of this.rows) {
        if (!rowItem.item) {
          continue
        }
        const connection = this.getConnectionsForRow(rowItem)

        if (!!connection && !!connection.connection.path) {
          out.push(connection)
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
      const message = this.$t(this.getConnectionErrorMessage(child, parentRow))
      const connectionPath = this.getConnectionPath(child.row, parent)
      const connection = {
        isValid: connectionValid && parentValid && childValid,
        isHighlighted: false,
        message,
        showMessage: true,
        ...connectionPath,
      }
      return Vue.observable({
        child: child.row,
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
     * Returns a connection information: path, start/end points, bounding box, anchor point, remove connection marker.
     *
     * @param child
     * @param parent
     * @returns {{path: *, startPoint: *, endPoint: *, anchorPoint: *, boundingBox: {x, y, width, height}, showRemovePath: boolean, removePath: string}|null}
     */
    getConnectionPath(child, parent) {
      const start = this.getRowFromBuffer(parent.id)
      const end = this.getRowFromBuffer(child.id)

      const startPosition = this.getRowPosition(start)
      const endPosition = this.getRowPosition(end)

      if (!endPosition || !startPosition) {
        return null
      }
      const { startPoint, endPoint, anchorPoint, path, bearingName } =
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
        bearingName,
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
      const startPoint = this.getPointBearingSE(parentPosition)
      const endPoint = this.getPointBearingW(childPosition)
      const { anchorPoint, commands } = this.getConnectionPathCommandsSE(
        startPoint,
        endPoint
      )

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },

    getConnectionPathCommandsSE(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundRightDown())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(-ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndRight())
      return { commands, anchorPoint }
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
      const startPoint = this.getPointBearingNE(parentPosition)
      const endPoint = this.getPointBearingW(childPosition)
      const { anchorPoint, commands } = this.getConnectionPathCommandsNE(
        startPoint,
        endPoint
      )

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },
    getConnectionPathCommandsNE(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundRightUp())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(-ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndRight())

      return { commands, anchorPoint }
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
      const startPoint = this.getPointBearingNW(parentPosition)
      const endPoint = this.getPointBearingE(childPosition)

      const { anchorPoint, commands } = this.getConnectionPathCommandsNW()

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },
    getConnectionPathCommandsNW(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }
      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundLeftUp())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(+ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndLeft())
      return { anchorPoint, commands }
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
      const startPoint = this.getPointBearingSW(parentPosition)
      const endPoint = this.getPointBearingE(childPosition)
      const { anchorPoint, commands } = this.getConnectionPathCommandsSW(
        startPoint,
        endPoint
      )

      return {
        startPoint,
        endPoint,
        anchorPoint,
        path: commands.join(' '),
      }
    },

    getConnectionPathCommandsSW(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }
      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      commands.push(movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine())
      commands.push(movePoint.commandRoundLeftDown())
      const anchorPoint = _.clone(movePoint)
      anchorPoint.movX(+ROUND_RADIUS)
      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndLeft())
      return { anchorPoint, commands }
    },

    /**
     * SW point position
     *
     *    +------+
     *    |      |
     *    +-X----+
     *
     * @param position
     * @returns {Point}
     */
    getPointBearingSW(position) {
      return new Point(
        position.left + HANDLER_POINT_OFFSET,
        position.top + position.height - ADJUST_FOR_PADDING
      )
    },
    /**
     * NW point position
     *
     *    +-X----+
     *    |      |
     *    +------+
     *
     * @param position
     * @returns {Point}
     */
    getPointBearingNW(position) {
      return new Point(
        position.left + HANDLER_POINT_OFFSET,
        position.top + ADJUST_FOR_PADDING
      )
    },

    /**
     * NE point position
     *
     *    +----X-+
     *    |      |
     *    +------+
     *
     * @param position
     * @returns {Point}
     */
    getPointBearingNE(position) {
      return new Point(
        position.left + position.width - HANDLER_POINT_OFFSET,
        position.top + ADJUST_FOR_PADDING
      )
    },

    /**
     * SE point position
     *
     *    +------+
     *    |      |
     *    +----x-+
     *
     * @param position
     * @returns {Point}
     */

    getPointBearingSE(position) {
      return new Point(
        position.left + position.width - HANDLER_POINT_OFFSET,
        position.top + position.height - ADJUST_FOR_PADDING
      )
    },

    /**
     * E point position
     *
     *    +------+
     *    |      X
     *    +------+
     *
     * @param position
     * @returns {Point}
     */
    getPointBearingE(position) {
      return new Point(
        position.left + position.width - ADJUST_FOR_PADDING * 2,
        position.top + position.height - HANDLER_POINT_OFFSET
      )
    },

    /**
     * W point position
     *
     *    +------+
     *    X      |
     *    +------+
     *
     * @param position
     * @returns {Point}
     */

    getPointBearingW(position) {
      return new Point(
        position.left,
        position.top + position.height - HANDLER_POINT_OFFSET
      )
    },

    getConnectionBearingName(parentPosition, childPosition) {
      const bearing = []
      if (
        (childPosition.top || childPosition.y) >
        (parentPosition.top || parentPosition.y)
      ) {
        bearing.push('S')
      } else {
        bearing.push('N')
      }

      if (
        (childPosition.left || childPosition.x) >
        (parentPosition.left || parentPosition.x)
      ) {
        bearing.push('E')
      } else {
        bearing.push('W')
      }

      return bearing.join('')
    },
    /**
     * Calculates connection path using proper bearing handler.
     *
     * @param parentPosition
     * @param childPosition
     * @returns {*}
     */
    getConnectionBearingPath(parentPosition, childPosition) {
      const bearing = this.getConnectionBearingName(
        parentPosition,
        childPosition
      )

      const bearingName = `getConnectionBearing${bearing}`
      return {
        bearingName,
        ...this[bearingName](parentPosition, childPosition),
      }
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

    async addConnection(parentRowId, childRowId) {
      const row = this.getRowFromBuffer(childRowId)?.item
      if (!row) {
        return
      }

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
      // do not create a connection which already exists
      const existing = oldValue.find((row) => row.id === parentRowId)
      if (existing) {
        return
      }
      value.push({ id: parentRowId })
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

    /**
     * Removes a connection between rows.
     *
     * @param connection
     * @param event
     * @returns {Promise<void>}
     */
    async onConnectionRemove(connection, event) {
      const parent = connection.parent
      const row = connection.child
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

    /**
     * Enable dragging elements
     *
     * @param rowId
     */
    dragSetupElements(rowId) {
      if (!rowId) {
        return
      }
      const currentRow = this.getRowFromBuffer(rowId)
      this.$refs.container.classList.add(
        'date-dependency__timeline-container--draggable'
      )
      document
        .getElementById(`row-${rowId}-activator`)
        ?.classList.add('date-dependency--no-events')
      document
        .getElementById(`row-${rowId}-droppable`)
        ?.classList.add('date-dependency--no-events')

      const fields = this.fields
      const rule = this.rule
      const field = fields.filter(
        (_field) => _field.id === rule.dependency_linkrow_field_id
      )[0]

      const fieldName = `field_${field.id}`

      const noEvents = []

      // disable drop zones in direct children
      this.rows.forEach((rowItem) => {
        const row = rowItem.item
        if (
          row[fieldName].findIndex((rowValue) => {
            return rowValue.id === rowId
          })
        ) {
          const childRowId = row.id

          noEvents.push(document.getElementById(`row-${childRowId}-activator`))

          noEvents.push(document.getElementById(`row-${childRowId}-droppable`))
        }
      })

      // disable drop zones in direct parents
      // currentRow.item[fieldName].forEach((row) => {
      //   const childRowId = row.id
      //   noEvents.push(document.getElementById(`row-${childRowId}-activator`))
      //
      //   noEvents.push(document.getElementById(`row-${childRowId}-droppable`))
      // })
      noEvents.forEach((elm) => {
         elm.classList.add('date-dependency--no-events')
      })
    },

    /**
     * Cleanup after drag is finished.
     *
     * @param rowId
     */
    dragClearElements(rowId) {
      this.$refs.container.classList.remove(
        'date-dependency__timeline-container--draggable'
      )
      Array.from(
        document.getElementsByClassName('date-dependency--no-events')
      ).forEach((elm) => {
        elm.classList.remove('date-dependency--no-events')
      })
      this.dragPoint.x = 0
      this.dragPoint.y = 0
      this.dragStartPoint = null
      this.drawConnection = null
    },
    onDragStart(event) {
      if (this.dragStartPoint) {
        return
      }
      this.dragPoint.x = event.offsetX
      this.dragPoint.y = event.offsetY
      const rowId = Number.parseInt(event.target.dataset.rowId)
      const startPoint = new Point(event.offsetX, event.offsetY)
      startPoint.rowId = rowId
      this.dragStartPoint = startPoint

      this.dragSetupElements(rowId)
    },
    async onDragEnd(event) {
      const rowId = Number.parseInt(this.dragStartPoint?.rowId)
      this.dragClearElements(rowId)
      if (!rowId || Number.isNaN(rowId)) {
        return
      }
      const dropZone = event.target
      const targetRowId = Number.parseInt(dropZone.dataset.rowId)
      if (!targetRowId) {
        return
      }
      await this.addConnection(rowId, targetRowId)
    },
    onDragMove(event) {
      if (this.dragStartPoint) {
        this.dragPoint.x = event.offsetX
        this.dragPoint.y = event.offsetY
        const bearing = this.getConnectionBearingName(
          this.dragStartPoint,
          this.dragPoint
        )
        const { commands } = this[`getConnectionPathCommands${bearing}`](
          this.dragStartPoint,
          this.dragPoint
        )
        const path = commands.join('')
        this.drawConnection = path
      }
    },
  },
}
</script>
<style></style>
