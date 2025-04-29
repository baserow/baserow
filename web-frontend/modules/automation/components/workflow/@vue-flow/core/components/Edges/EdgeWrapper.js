import {
  computed,
  defineComponent,
  getCurrentInstance,
  h,
  inject,
  provide,
  ref,
} from 'vue'
import { useEdgeHooks, useHandle, useVueFlow } from '../../composables'
import { EdgeId, EdgeRef, Slots } from '../../context'
import {
  ARIA_EDGE_DESC_KEY,
  ErrorCode,
  VueFlowError,
  elementSelectionKeys,
  getEdgeHandle,
  getHandlePosition,
  getMarkerId,
} from '../../utils'
import EdgeAnchor from './EdgeAnchor'

// Définition locale des énumérations
const ConnectionMode = {
  Strict: 'strict',
  Loose: 'loose',
}

const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

const EdgeWrapper = defineComponent({
  name: 'Edge',
  compatConfig: { MODE: 3 },
  props: ['id'],
  setup(props) {
    const {
      id: vueFlowId,
      addSelectedEdges,
      connectionMode,
      edgeUpdaterRadius,
      emits,
      nodesSelectionActive,
      noPanClassName,
      getEdgeTypes,
      removeSelectedEdges,
      findEdge,
      findNode,
      isValidConnection,
      multiSelectionActive,
      disableKeyboardA11y,
      elementsSelectable,
      edgesUpdatable,
      edgesFocusable,
      hooks,
    } = useVueFlow()

    const edge = computed(() => findEdge(props.id))

    const { emit, on } = useEdgeHooks(edge.value, emits)

    const slots = inject(Slots)

    const instance = getCurrentInstance()

    const mouseOver = ref(false)

    const updating = ref(false)

    const nodeId = ref('')

    const handleId = ref(null)

    const edgeUpdaterType = ref('source')

    const edgeEl = ref(null)

    const isSelectable = computed(() =>
      typeof edge.value.selectable === 'undefined'
        ? elementsSelectable.value
        : edge.value.selectable
    )

    const isUpdatable = computed(() =>
      typeof edge.value.updatable === 'undefined'
        ? edgesUpdatable.value
        : edge.value.updatable
    )

    const isFocusable = computed(() =>
      typeof edge.value.focusable === 'undefined'
        ? edgesFocusable.value
        : edge.value.focusable
    )

    provide(EdgeId, props.id)
    provide(EdgeRef, edgeEl)

    const edgeClass = computed(() =>
      edge.value.class instanceof Function
        ? edge.value.class(edge.value)
        : edge.value.class
    )

    const edgeStyle = computed(() =>
      edge.value.style instanceof Function
        ? edge.value.style(edge.value)
        : edge.value.style
    )

    const edgeCmp = computed(() => {
      const name = edge.value.type || 'default'

      const slot = slots?.[`edge-${name}`]
      if (slot) {
        return slot
      }

      let edgeType = edge.value.template ?? getEdgeTypes.value[name]

      if (typeof edgeType === 'string' && instance) {
        const appContext =
          instance.proxy?.$root?.$options?.context?.components || {}
        const components = Object.keys(appContext)
        if (components && components.includes(name)) {
          // Résolution simplifiée pour Vue 2.7
          edgeType = appContext[name]
        }
      }

      if (edgeType && typeof edgeType !== 'string') {
        return edgeType
      }

      emits.error(new VueFlowError(ErrorCode.EDGE_TYPE_MISSING, edgeType))

      return false
    })

    const { handlePointerDown } = useHandle({
      nodeId,
      handleId,
      type: edgeUpdaterType,
      isValidConnection,
      edgeUpdaterType,
      onEdgeUpdate,
      onEdgeUpdateEnd,
    })

    return () => {
      const sourceNode = findNode(edge.value.source)
      const targetNode = findNode(edge.value.target)
      const pathOptions =
        'pathOptions' in edge.value ? edge.value.pathOptions : {}

      if (!sourceNode && !targetNode) {
        emits.error(
          new VueFlowError(
            ErrorCode.EDGE_SOURCE_TARGET_MISSING,
            edge.value.id,
            edge.value.source,
            edge.value.target
          )
        )

        return null
      }

      if (!sourceNode) {
        emits.error(
          new VueFlowError(
            ErrorCode.EDGE_SOURCE_MISSING,
            edge.value.id,
            edge.value.source
          )
        )

        return null
      }

      if (!targetNode) {
        emits.error(
          new VueFlowError(
            ErrorCode.EDGE_TARGET_MISSING,
            edge.value.id,
            edge.value.target
          )
        )

        return null
      }

      if (
        !edge.value ||
        edge.value.hidden ||
        sourceNode.hidden ||
        targetNode.hidden
      ) {
        return null
      }

      let sourceNodeHandles
      if (connectionMode.value === ConnectionMode.Strict) {
        sourceNodeHandles = sourceNode.handleBounds.source
      } else {
        sourceNodeHandles = [
          ...(sourceNode.handleBounds.source || []),
          ...(sourceNode.handleBounds.target || []),
        ]
      }

      const sourceHandle = getEdgeHandle(
        sourceNodeHandles,
        edge.value.sourceHandle
      )

      let targetNodeHandles
      if (connectionMode.value === ConnectionMode.Strict) {
        targetNodeHandles = targetNode.handleBounds.target
      } else {
        targetNodeHandles = [
          ...(targetNode.handleBounds.target || []),
          ...(targetNode.handleBounds.source || []),
        ]
      }

      const targetHandle = getEdgeHandle(
        targetNodeHandles,
        edge.value.targetHandle
      )

      const sourcePosition = sourceHandle?.position || Position.Bottom

      const targetPosition = targetHandle?.position || Position.Top

      const { x: sourceX, y: sourceY } = getHandlePosition(
        sourceNode,
        sourceHandle,
        sourcePosition
      )
      const { x: targetX, y: targetY } = getHandlePosition(
        targetNode,
        targetHandle,
        targetPosition
      )

      // Mise à jour des propriétés de position
      edge.value.sourceX = sourceX
      edge.value.sourceY = sourceY
      edge.value.targetX = targetX
      edge.value.targetY = targetY

      // Extraction des propriétés des edges dans un objet pour transmission au slot
      const edgeData = {
        id: props.id,
        sourceNode,
        targetNode,
        source: edge.value.source,
        target: edge.value.target,
        type: edge.value.type,
        updatable: isUpdatable.value,
        selected: edge.value.selected,
        animated: edge.value.animated,
        label: edge.value.label,
        labelStyle: edge.value.labelStyle,
        labelShowBg: edge.value.labelShowBg,
        labelBgStyle: edge.value.labelBgStyle,
        labelBgPadding: edge.value.labelBgPadding,
        labelBgBorderRadius: edge.value.labelBgBorderRadius,
        data: edge.value.data,
        events: { ...edge.value.events, ...on },
        style: edgeStyle.value,
        markerStart: `url('#${getMarkerId(
          edge.value.markerStart,
          vueFlowId
        )}')`,
        markerEnd: `url('#${getMarkerId(edge.value.markerEnd, vueFlowId)}')`,
        sourcePosition,
        targetPosition,
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourceHandleId: edge.value.sourceHandle,
        targetHandleId: edge.value.targetHandle,
        interactionWidth: edge.value.interactionWidth,
        ...pathOptions,
      }

      return h(
        'g',
        {
          ref: edgeEl,
          key: props.id,
          class: [
            'vue-flow__edge',
            `vue-flow__edge-${
              edgeCmp.value === false ? 'default' : edge.value.type || 'default'
            }`,
            noPanClassName.value,
            edgeClass.value,
            {
              updating: mouseOver.value,
              selected: edge.value.selected,
              animated: edge.value.animated,
              inactive:
                !isSelectable.value && !hooks.value.edgeClick.hasListeners(),
            },
          ],
          on: {
            click: onEdgeClick,
            contextmenu: onEdgeContextMenu,
            dblclick: onDoubleClick,
            mouseenter: onEdgeMouseEnter,
            mousemove: onEdgeMouseMove,
            mouseleave: onEdgeMouseLeave,
            keydown: isFocusable.value ? onKeyDown : undefined,
          },
          attrs: {
            'data-id': props.id,
            tabindex: isFocusable.value ? 0 : undefined,
            'aria-label':
              edge.value.ariaLabel === null
                ? undefined
                : edge.value.ariaLabel ||
                  `Edge from ${edge.value.source} to ${edge.value.target}`,
            'aria-describedby': isFocusable.value
              ? `${ARIA_EDGE_DESC_KEY}-${vueFlowId}`
              : undefined,
            role: isFocusable.value ? 'button' : 'img',
          },
        },
        [
          updating.value
            ? null
            : slots?.[`edge-${edge.value.type || 'default'}`]
            ? slots[`edge-${edge.value.type || 'default'}`](edgeData)
            : h(
                edgeCmp.value === false
                  ? getEdgeTypes.value.default
                  : edgeCmp.value,
                {
                  props: edgeData,
                }
              ),
          [
            isUpdatable.value === 'source' || isUpdatable.value === true
              ? [
                  h(
                    'g',
                    {
                      on: {
                        mousedown: onEdgeUpdaterSourceMouseDown,
                        mouseenter: onEdgeUpdaterMouseEnter,
                        mouseout: onEdgeUpdaterMouseOut,
                      },
                    },
                    h(EdgeAnchor, {
                      position: sourcePosition,
                      centerX: sourceX,
                      centerY: sourceY,
                      radius: edgeUpdaterRadius.value,
                      type: 'source',
                      attrs: {
                        'data-type': 'source',
                      },
                    })
                  ),
                ]
              : null,
            isUpdatable.value === 'target' || isUpdatable.value === true
              ? [
                  h(
                    'g',
                    {
                      on: {
                        mousedown: onEdgeUpdaterTargetMouseDown,
                        mouseenter: onEdgeUpdaterMouseEnter,
                        mouseout: onEdgeUpdaterMouseOut,
                      },
                    },
                    h(EdgeAnchor, {
                      position: targetPosition,
                      centerX: targetX,
                      centerY: targetY,
                      radius: edgeUpdaterRadius.value,
                      type: 'target',
                      attrs: {
                        'data-type': 'target',
                      },
                    })
                  ),
                ]
              : null,
          ],
        ]
      )
    }

    function onEdgeUpdaterMouseEnter() {
      mouseOver.value = true
    }

    function onEdgeUpdaterMouseOut() {
      mouseOver.value = false
    }

    function onEdgeUpdate(event, connection) {
      emit.update({ event, edge: edge.value, connection })
    }

    function onEdgeUpdateEnd(event) {
      emit.updateEnd({ event, edge: edge.value })
      updating.value = false
    }

    function handleEdgeUpdater(event, isSourceHandle) {
      if (event.button !== 0) {
        return
      }

      updating.value = true

      nodeId.value = isSourceHandle ? edge.value.target : edge.value.source
      handleId.value =
        (isSourceHandle ? edge.value.targetHandle : edge.value.sourceHandle) ??
        null

      edgeUpdaterType.value = isSourceHandle ? 'target' : 'source'

      emit.updateStart({ event, edge: edge.value })

      handlePointerDown(event)
    }

    function onEdgeClick(event) {
      const data = { event, edge: edge.value }

      if (isSelectable.value) {
        nodesSelectionActive.value = false

        if (edge.value.selected && multiSelectionActive.value) {
          removeSelectedEdges([edge.value])

          edgeEl.value?.blur()
        } else {
          addSelectedEdges([edge.value])
        }
      }

      emit.click(data)
    }

    function onEdgeContextMenu(event) {
      emit.contextMenu({ event, edge: edge.value })
    }

    function onDoubleClick(event) {
      emit.doubleClick({ event, edge: edge.value })
    }

    function onEdgeMouseEnter(event) {
      emit.mouseEnter({ event, edge: edge.value })
    }

    function onEdgeMouseMove(event) {
      emit.mouseMove({ event, edge: edge.value })
    }

    function onEdgeMouseLeave(event) {
      emit.mouseLeave({ event, edge: edge.value })
    }

    function onEdgeUpdaterSourceMouseDown(event) {
      handleEdgeUpdater(event, true)
    }

    function onEdgeUpdaterTargetMouseDown(event) {
      handleEdgeUpdater(event, false)
    }

    function onKeyDown(event) {
      if (
        !disableKeyboardA11y.value &&
        elementSelectionKeys.includes(event.key) &&
        isSelectable.value
      ) {
        const unselect = event.key === 'Escape'

        if (unselect) {
          edgeEl.value?.blur()

          removeSelectedEdges([findEdge(props.id)])
        } else {
          addSelectedEdges([findEdge(props.id)])
        }
      }
    }
  },
})

export default EdgeWrapper
