<template>
  <div
    v-if="rule.dependency_linkrow_field_id"
    ref="container"
    class="date-dependency__timeline-container"
    :class="{
      'date-dependency__timeline-container--draggable': !!drawConnection,
    }"
  >
    <svg
      class="date-dependency__drawable"
      :class="{ 'date-dependency__drawable--draggable': !!drawConnection }"
      :width="width"
      :height="height"
      @mousedown="onDragStart($event)"
      @mousemove="onDragMove($event)"
      @mouseup="onDragEnd($event)"
    >
      <g v-for="dz in dropZones" :key="dz.row.item.id">
        <rect
          :id="`row-${dz.row.item.id}-droppable`"
          class="date-dependency__drop-zone"
          :x="dz.position.left - 10"
          :y="dz.position.top - 10"
          :width="dz.position.width + 20"
          :height="dz.position.height + 20"
          :data-row-id="dz.row.item.id"
        />
      </g>

      <g v-for="(rowItem, rindex) in renderableRows" :key="`row-${rindex}`">
        <g
          v-for="(connection, cindex) in connections[rowItem.item.id]"
          :key="`row-connection-${cindex}`"
          class="date-dependency__connection-group"
        >
          <path
            class="date-dependency__path"
            :class="{
              'date-dependency__path--invalid': !connection.connection.isValid,
            }"
            :d="connection.connection.path"
            @dblclick="onConnectionRemove(connection, $event)"
          />

          <text
            v-if="connection.connection.message"
            class="date-dependency__text"
            :class="{
              'date-dependency__text--invalid': !connection.connection.isValid,
            }"
            :x="connection.connection.anchorPoint.x + 6"
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
import {
  ADJUST_FOR_PADDING,
  DateDependencyRow,
  HANDLER_POINT_OFFSET,
  Point,
  ROUND_RADIUS,
  ROW_HANDLE_DIRECTIONS,
} from '@baserow_enterprise/dateDependencyTypes'
import _ from 'lodash'

export default {
  inject: ['getRowPosition'],
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
    renderableRows() {
      return this.rows.filter((rowItem) => {
        return !!rowItem.item?.id
      })
    },
    dropZones() {
      const dropZones = []
      this.renderableRows.forEach((row) => {
        const position = this.getRowPosition(row)
        dropZones.push({ row, position })
      })
      return dropZones
    },

    connections() {
      const connections = {}
      this.renderableRows.forEach((rowItem) => {
        const rowConnections = this.getConnectionsForRow(rowItem)
        if (rowConnections) {
          connections[rowItem.item.id] = rowConnections
        }
      })
      return connections
    },
  },
  methods: {
    getRowFromBuffer(rowId) {
      return this.rows.find((row) => {
        return !!row.item && row.item?.id === rowId
      })
    },
    getHandlePointsForRow(rowItem) {
      const out = []
      const rowPosition = this.getRowPosition(rowItem)
      if (!rowPosition) {
        return out
      }

      for (const direction of ROW_HANDLE_DIRECTIONS) {
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

      const anyFetching = child.isFetching() || parentRow.isFetching()
      const connectionValid = this.isConnectionValid(child, parentRow)
      const errorMessage = this.getConnectionErrorMessage(child, parentRow)
      const message = errorMessage ? this.$t(errorMessage) : null
      const connectionPath = this.getConnectionPath(child.row, parent)
      const connection = {
        // if any row is being fetched, we ignore connection validity
        isValid: anyFetching || (connectionValid && parentValid && childValid),
        isHighlighted: false,
        message,
        showMessage: true,
        ...connectionPath,
      }
      const out = {
        child: child.row,
        parent: parentRow.row,
        parentRow,
        connection,
      }
      return out
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
     * @returns {{path: *, startPoint: *, endPoint: *, anchorPoint: *, showRemovePath: boolean, removePath: string}|null}
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

      return {
        path,
        startPoint,
        endPoint,
        anchorPoint,
        bearingName,
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

      const complexPath = startPoint.x > endPoint.x

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]
      let anchorPoint
      if (complexPath) {
        commands.push(movePoint.movY(ROUND_RADIUS).commandDrawLine())
        commands.push(
          movePoint
            .movX(-(ROUND_RADIUS + Math.abs(movePoint.x - endPoint.x)))
            .commandDrawLine()
        )

        const yDiff = endPoint.y - movePoint.y
        anchorPoint = _.clone(movePoint)
        anchorPoint.movY(yDiff / 2)

        commands.push(
          movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundRightDown())
      } else {
        commands.push(
          movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundRightDown())

        anchorPoint = _.clone(movePoint)
        anchorPoint.movX(-ROUND_RADIUS)
      }

      commands.push(endPoint.commandDrawLine())
      commands.push(endPoint.commandHorizontalArrowEndRight())
      return { commands, anchorPoint }
    },
    /**
     * NE bearing connection
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

      const complexPath = startPoint.x > endPoint.x

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]
      let anchorPoint
      if (complexPath) {
        const yDiff = endPoint.y - movePoint.y
        anchorPoint = _.clone(movePoint)
        anchorPoint.movY(yDiff / 2)
        commands.push(
          movePoint.setY(endPoint.y + 2 * ROUND_RADIUS).commandDrawLine()
        )

        commands.push(
          movePoint.setX(endPoint.x - ROUND_RADIUS).commandDrawLine()
        )
        commands.push(
          movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundRightUp())
      } else {
        commands.push(
          movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundRightUp())
        anchorPoint = _.clone(movePoint)
        anchorPoint.movX(-ROUND_RADIUS)
      }

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
      const parentEnd = parentPosition.left + parentPosition.width
      const childEnd = childPosition.left + childPosition.width
      let startPoint, endPoint, path

      if (parentPosition.left > childPosition.left && parentEnd > childEnd) {
        startPoint = this.getPointBearingNW(parentPosition)
        endPoint = this.getPointBearingE(childPosition)
        path = this.getConnectionPathCommandsNW(startPoint, endPoint)
      } else {
        startPoint = this.getPointBearingNW(parentPosition)
        endPoint = this.getPointBearingE(childPosition)
        path = this.getConnectionPathCommandsNW(startPoint, endPoint)
      }

      return {
        startPoint,
        endPoint,
        anchorPoint: path.anchorPoint,
        path: path.commands.join(' '),
      }
    },

    getConnectionPathCommandsNW(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }
      const complexPath = startPoint.x < endPoint.x

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]
      let anchorPoint, yDiff

      if (complexPath) {
        commands.push(
          movePoint.setY(endPoint.y + ROUND_RADIUS * 2).commandDrawLine()
        )

        yDiff = Math.abs(endPoint.y - startPoint.y)
        anchorPoint = _.clone(movePoint)
        anchorPoint.setX(startPoint.x)
        anchorPoint.movY(yDiff / 2)

        commands.push(
          movePoint.setX(endPoint.x + ROUND_RADIUS).commandDrawLine()
        )
        commands.push(
          movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine()
        )

        commands.push(movePoint.commandRoundLeftUp())
        commands.push(endPoint.commandHorizontalArrowEndLeft())
      } else {
        commands.push(
          movePoint.setY(endPoint.y + ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundLeftUp())
        yDiff = Math.abs(endPoint.y - startPoint.y)
        anchorPoint = _.clone(movePoint)
        anchorPoint.setX(startPoint.x)
        anchorPoint.movY(yDiff / 2)

        commands.push(endPoint.commandDrawLine())
        commands.push(endPoint.commandHorizontalArrowEndLeft())
      }

      return { anchorPoint, commands }
    },

    /**
     * SW bearing connection
     *
     *        [ parent ]
     *               |
     *   [ child ]<--+
     *
     * or
     *
     * @param parentPosition
     * @param childPosition
     */
    getConnectionBearingSW(parentPosition, childPosition) {
      let startPoint, endPoint, path

      if (parentPosition.left >= childPosition.left) {
        startPoint = this.getPointBearingSW(parentPosition)
        endPoint = this.getPointBearingW(childPosition)

        path = this.getConnectionPathCommandsSE(startPoint, endPoint)
      } else {
        startPoint = this.getPointBearingSW(parentPosition)
        endPoint = this.getPointBearingE(childPosition)

        path = this.getConnectionPathCommandsSW(startPoint, endPoint)
      }

      return {
        startPoint,
        endPoint,
        anchorPoint: path.anchorPoint,
        path: path.commands.join(' '),
      }
    },

    getConnectionPathCommandsSW(startPoint, endPoint) {
      if (!startPoint || !endPoint) {
        return { anchorPoint: new Point(0, 0), commands: [] }
      }

      const complexPath = startPoint.x < endPoint.x

      const movePoint = _.clone(startPoint)
      const commands = [movePoint.commandMove()]

      let anchorPoint

      if (complexPath) {
        commands.push(movePoint.movY(ROUND_RADIUS).commandDrawLine())
        commands.push(
          movePoint
            .movX(-(ROUND_RADIUS + Math.abs(movePoint.x - endPoint.x)))
            .commandDrawLine()
        )
        const yDiff = endPoint.y - movePoint.y
        anchorPoint = _.clone(movePoint)
        anchorPoint.movY(yDiff / 2)
        commands.push(
          movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundRightDown())
      } else {
        commands.push(
          movePoint.setY(endPoint.y - ROUND_RADIUS).commandDrawLine()
        )
        commands.push(movePoint.commandRoundLeftDown())
        anchorPoint = _.clone(movePoint)
        anchorPoint.movX(+ROUND_RADIUS)
      }

      commands.push(endPoint.commandDrawLine())
      if (complexPath) {
        commands.push(endPoint.commandHorizontalArrowEndRight())
      } else {
        commands.push(endPoint.commandHorizontalArrowEndLeft())
      }
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

    /**
     * Detects which path shape should be used for a connection between a parent and
     * a child row. The path is calculated from the parent to the child.
     *
     * A connection shape is described as a bearing name (i.e. `SW` means South-West,
     * the path should go down and left), but in some cases (i.e. a child starts after
     * parent's start and ends before parent's end), paths will be more complex, so
     * the naming may have extra particles to distinct from a simple path.
     *
     * @param parentPosition
     * @param childPosition
     * @returns {(*&{bearingName: string})|*|string}
     */
    getConnectionBearingName(parentPosition, childPosition) {
      // Negative values of parentToChild means that the child starts
      // before the parent.
      const parentToChildX =
        (childPosition.left || childPosition.x) -
        (parentPosition.left || parentPosition.x)

      const parentToChildY =
        (childPosition.top || childPosition.y) -
        (parentPosition.top || parentPosition.y)

      // Main outgoing directions
      const bearing = []
      if (parentToChildY < 0) {
        bearing.push('N')
      } else {
        bearing.push('S')
      }

      if (parentToChildX < 0) {
        bearing.push('W')
      } else {
        bearing.push('E')
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
      const data = this[bearingName](parentPosition, childPosition)
      return {
        bearingName,
        ...data,
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
      if (parentRowId === childRowId) {
        return
      }
      const row = this.getRowFromBuffer(childRowId)?.item
      if (!row) {
        return
      }

      const storePrefix = this.storePrefix
      const view = this.view
      const table = this.view.table
      const fields = this.fields
      const rule = this.rule
      const field = fields.find(
        (_field) => _field.id === rule.dependency_linkrow_field_id
      )

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
      // We should not allow to remove a connection if any row is moved in the same time,
      // as this may be an accidental click.
      const rowsDragging = document.getElementsByClassName(
        'timeline-grid-row--dragging'
      )

      if (rowsDragging.length > 0) {
        return
      }
      const parent = connection.parent
      const row = connection.child
      const storePrefix = this.storePrefix
      const view = this.view
      const table = this.view.table
      const fields = this.fields
      const rule = this.rule
      const field = fields.find(
        (_field) => _field.id === rule.dependency_linkrow_field_id
      )

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
     * Cleanup after drag is finished.
     *
     * @param rowId
     */
    dragClearElements() {
      this.dragPoint.x = 0
      this.dragPoint.y = 0
      this.dragStartPoint = null
      this.drawConnection = null
      Array.from(
        document.getElementsByClassName('date-dependency__drop-zone--droppable')
      ).forEach((el) => {
        el.classList.remove('date-dependency__drop-zone--droppable')
      })
    },

    dragStartElements() {
      Array.from(
        document.getElementsByClassName('date-dependency__drop-zone')
      ).forEach((el) => {
        el.classList.add('date-dependency__drop-zone--droppable')
      })
    },

    onDragStart(event) {
      if (this.dragStartPoint) {
        return
      }
      this.dragStartElements()

      this.dragPoint.x = event.offsetX
      this.dragPoint.y = event.offsetY
      const rowId = Number.parseInt(event.target.dataset.rowId)
      const startPoint = new Point(event.offsetX, event.offsetY)
      startPoint.rowId = rowId
      this.dragStartPoint = startPoint
    },
    async onDragEnd(event) {
      const rowId = Number.parseInt(this.dragStartPoint?.rowId)
      this.dragClearElements()
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
        const path = commands.join(' ')
        this.drawConnection = path
      }
    },
  },
}
</script>
