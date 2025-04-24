import {
  computed,
  defineComponent,
  getCurrentInstance,
  h,
  inject,
  nextTick,
  onMounted,
  provide,
  ref,
  watch,
} from 'vue'
import {
  ARIA_NODE_DESC_KEY,
  ErrorCode,
  VueFlowError,
  arrowKeyDiffs,
  calcNextPosition,
  elementSelectionKeys,
  getXYZPos,
  handleNodeClick,
  snapPosition,
} from '../../utils'
import { NodeId, NodeRef, Slots } from '../../context'
import {
  isInputDOMNode,
  useDrag,
  useNode,
  useNodeHooks,
  useUpdateNodePositions,
  useVueFlow,
} from '../../composables'

const NodeWrapper = defineComponent({
  name: 'Node',
  compatConfig: { MODE: 3 },
  props: ['id', 'resizeObserver'],
  setup(props) {
    const {
      id: vueFlowId,
      noPanClassName,
      selectNodesOnDrag,
      nodesSelectionActive,
      multiSelectionActive,
      emits,
      removeSelectedNodes,
      addSelectedNodes,
      updateNodeDimensions,
      onUpdateNodeInternals,
      getNodeTypes,
      nodeExtent,
      elevateNodesOnSelect,
      disableKeyboardA11y,
      ariaLiveMessage,
      snapToGrid,
      snapGrid,
      nodeDragThreshold,
      nodesDraggable,
      elementsSelectable,
      nodesConnectable,
      nodesFocusable,
      hooks,
    } = useVueFlow()

    const nodeElement = ref(null)
    provide(NodeRef, nodeElement)
    provide(NodeId, props.id)

    const slots = inject(Slots)

    const instance = getCurrentInstance()

    const updateNodePositions = useUpdateNodePositions()

    const { node, parentNode } = useNode(props.id)

    const { emit } = useNodeHooks(node, emits)

    const isDraggable = computed(() =>
      typeof node.draggable === 'undefined'
        ? nodesDraggable.value
        : node.draggable
    )

    const isSelectable = computed(() =>
      typeof node.selectable === 'undefined'
        ? elementsSelectable.value
        : node.selectable
    )

    const isConnectable = computed(() =>
      typeof node.connectable === 'undefined'
        ? nodesConnectable.value
        : node.connectable
    )

    const isFocusable = computed(() =>
      typeof node.focusable === 'undefined'
        ? nodesFocusable.value
        : node.focusable
    )

    const hasPointerEvents = computed(
      () =>
        isSelectable.value ||
        isDraggable.value ||
        hooks.value.nodeClick.hasListeners() ||
        hooks.value.nodeDoubleClick.hasListeners() ||
        hooks.value.nodeMouseEnter.hasListeners() ||
        hooks.value.nodeMouseMove.hasListeners() ||
        hooks.value.nodeMouseLeave.hasListeners()
    )

    const isInit = computed(
      () => !!node.dimensions.width && !!node.dimensions.height
    )

    const nodeCmp = computed(() => {
      const name = node.type || 'default'

      const slot = slots?.[`node-${name}`]
      if (slot) {
        return slot
      }

      let nodeType = node.template || getNodeTypes.value[name]

      if (typeof nodeType === 'string' && instance) {
        const appContext =
          instance.proxy?.$root?.$options?.context?.components || {}
        const components = Object.keys(appContext)
        if (components && components.includes(name)) {
          nodeType = appContext[name]
        }
      }

      if (nodeType && typeof nodeType !== 'string') {
        return nodeType
      }

      emits.error(new VueFlowError(ErrorCode.NODE_TYPE_MISSING, nodeType))

      return false
    })

    const dragging = useDrag({
      id: props.id,
      el: nodeElement,
      disabled: () => !isDraggable.value,
      selectable: isSelectable,
      dragHandle: () => node.dragHandle,
      onStart(event) {
        console.log('onStart', event)
        emit.dragStart(event)
      },
      onDrag(event) {
        console.log('onStart', event)
        emit.drag(event)
      },
      onStop(event) {
        emit.dragStop(event)
      },
      onClick(event) {
        onSelectNode(event)
      },
    })

    const getClass = computed(() =>
      node.class instanceof Function ? node.class(node) : node.class
    )

    const getStyle = computed(() => {
      const styles =
        (node.style instanceof Function ? node.style(node) : node.style) || {}

      const width =
        node.width instanceof Function ? node.width(node) : node.width
      const height =
        node.height instanceof Function ? node.height(node) : node.height

      if (!styles.width && width) {
        styles.width = typeof width === 'string' ? width : `${width}px`
      }

      if (!styles.height && height) {
        styles.height = typeof height === 'string' ? height : `${height}px`
      }

      return styles
    })

    const zIndex = computed(() =>
      Number(node.zIndex ?? getStyle.value.zIndex ?? 0)
    )

    onUpdateNodeInternals((updateIds) => {
      // when no ids are passed, update all nodes
      if (updateIds.includes(props.id) || !updateIds.length) {
        updateInternals()
      }
    })

    onMounted(() => {
      watch(
        () => node.hidden,
        (isHidden = false, _, onCleanup) => {
          if (!isHidden && nodeElement.value) {
            props.resizeObserver.observe(nodeElement.value)

            onCleanup(() => {
              if (nodeElement.value) {
                props.resizeObserver.unobserve(nodeElement.value)
              }
            })
          }
        },
        { immediate: true, flush: 'post' }
      )
    })

    watch(
      [() => node.type, () => node.sourcePosition, () => node.targetPosition],
      () => {
        nextTick(() => {
          updateNodeDimensions([
            { id: props.id, nodeElement: nodeElement.value, forceUpdate: true },
          ])
        })
      }
    )

    /** this watcher only updates XYZPosition (when dragging a parent etc) */
    watch(
      [
        () => node.position.x,
        () => node.position.y,
        () => parentNode.value?.computedPosition.x,
        () => parentNode.value?.computedPosition.y,
        () => parentNode.value?.computedPosition.z,
        zIndex,
        () => node.selected,
        () => node.dimensions.height,
        () => node.dimensions.width,
        () => parentNode.value?.dimensions.height,
        () => parentNode.value?.dimensions.width,
      ],
      ([newX, newY, parentX, parentY, parentZ, nodeZIndex]) => {
        const xyzPos = {
          x: newX,
          y: newY,
          z:
            nodeZIndex +
            (elevateNodesOnSelect.value ? (node.selected ? 1000 : 0) : 0),
        }

        if (typeof parentX !== 'undefined' && typeof parentY !== 'undefined') {
          node.computedPosition = getXYZPos(
            { x: parentX, y: parentY, z: parentZ },
            xyzPos
          )
        } else {
          node.computedPosition = xyzPos
        }
      },
      { flush: 'post', immediate: true }
    )

    watch(
      [() => node.extent, nodeExtent],
      ([nodeExtent, globalExtent], [oldNodeExtent, oldGlobalExtent]) => {
        // update position if extent has actually changed
        if (nodeExtent !== oldNodeExtent || globalExtent !== oldGlobalExtent) {
          clampPosition()
        }
      }
    )

    // clamp initial position to nodes' extent
    // if extent is parent, we need dimensions to properly clamp the position
    if (
      node.extent === 'parent' ||
      (typeof node.extent === 'object' &&
        'range' in node.extent &&
        node.extent.range === 'parent')
    ) {
      // Adaptation pour Vue 2.7 - on peut utiliser une simple fonction qui vérifie la condition
      const checkInitialized = () => {
        if (isInit.value) {
          clampPosition()
        } else {
          setTimeout(checkInitialized, 50)
        }
      }
      checkInitialized()
    }
    // if extent is not parent, we can clamp it immediately
    else {
      clampPosition()
    }

    return () => {
      if (node.hidden) {
        return null
      }

      // Noter le changement ici pour Vue 2.7 - comment nous gérons les slots
      // Modification pour Vue 2.7 des slots nommés
      const nodeData = {
        id: node.id,
        type: node.type,
        data: node.data,
        selected: node.selected,
        dragging: dragging?.value,
        connectable: isConnectable.value,
        position: node.computedPosition,
        dimensions: node.dimensions,
        isValidTargetPos: node.isValidTargetPos,
        isValidSourcePos: node.isValidSourcePos,
        targetPosition: node.targetPosition,
        sourcePosition: node.sourcePosition,
        label: node.label || '',
      }

      return h(
        'div',
        {
          ref: nodeElement,
          class: [
            'vue-flow__node',
            `vue-flow__node-${
              nodeCmp.value === false ? 'default' : node.type || 'default'
            }`,
            {
              [noPanClassName.value]: isDraggable.value,
              dragging: dragging?.value,
              draggable: isDraggable.value,
              selected: node.selected,
              selectable: isSelectable.value,
              parent: node.isParent,
            },
            getClass.value,
          ],
          style: {
            visibility: isInit.value ? 'visible' : 'hidden',
            zIndex: node.computedPosition.z ?? zIndex.value,
            transform: `translate(${node.computedPosition.x}px,${node.computedPosition.y}px)`,
            pointerEvents: hasPointerEvents.value ? 'all' : 'none',
            ...getStyle.value,
          },
          attrs: {
            'data-id': node.id,
            tabindex: isFocusable.value ? 0 : undefined,
            role: isFocusable.value ? 'button' : undefined,
            'aria-describedby': disableKeyboardA11y.value
              ? undefined
              : `${ARIA_NODE_DESC_KEY}-${vueFlowId}`,
            'aria-label': node.ariaLabel,
          },
          on: {
            mouseenter: onMouseEnter,
            mousemove: onMouseMove,
            mouseleave: onMouseLeave,
            contextmenu: onContextMenu,
            click: onSelectNode,
            dblclick: onDoubleClick,
            keydown: onKeyDown,
          },
        },
        [
          // Vérifier si nous avons un slot pour ce type de nœud
          slots?.[`node-${node.type || 'default'}`]
            ? slots[`node-${node.type || 'default'}`](nodeData)
            : h(
                nodeCmp.value === false
                  ? getNodeTypes.value.default
                  : nodeCmp.value,
                {
                  props: nodeData,
                }
              ),
        ]
      )
    }

    /** this re-calculates the current position, necessary for clamping by a node's extent */
    function clampPosition() {
      const nextPosition = node.computedPosition

      const { computedPosition, position } = calcNextPosition(
        node,
        snapToGrid.value
          ? snapPosition(nextPosition, snapGrid.value)
          : nextPosition,
        emits.error,
        nodeExtent.value,
        parentNode.value
      )

      // only overwrite positions if there are changes when clamping
      if (
        node.computedPosition.x !== computedPosition.x ||
        node.computedPosition.y !== computedPosition.y
      ) {
        node.computedPosition = {
          ...node.computedPosition,
          ...computedPosition,
        }
      }

      if (node.position.x !== position.x || node.position.y !== position.y) {
        node.position = position
      }
    }

    function updateInternals() {
      if (nodeElement.value) {
        updateNodeDimensions([
          { id: props.id, nodeElement: nodeElement.value, forceUpdate: true },
        ])
      }
    }

    function onMouseEnter(event) {
      if (!dragging?.value) {
        emit.mouseEnter({ event, node })
      }
    }

    function onMouseMove(event) {
      if (!dragging?.value) {
        emit.mouseMove({ event, node })
      }
    }

    function onMouseLeave(event) {
      if (!dragging?.value) {
        emit.mouseLeave({ event, node })
      }
    }

    function onContextMenu(event) {
      return emit.contextMenu({ event, node })
    }

    function onDoubleClick(event) {
      return emit.doubleClick({ event, node })
    }

    function onSelectNode(event) {
      if (
        isSelectable.value &&
        (!selectNodesOnDrag.value ||
          !isDraggable.value ||
          nodeDragThreshold.value > 0)
      ) {
        handleNodeClick(
          node,
          multiSelectionActive.value,
          addSelectedNodes,
          removeSelectedNodes,
          nodesSelectionActive,
          false,
          nodeElement.value
        )
      }

      emit.click({ event, node })
    }

    function onKeyDown(event) {
      if (isInputDOMNode(event) || disableKeyboardA11y.value) {
        return
      }

      if (elementSelectionKeys.includes(event.key) && isSelectable.value) {
        const unselect = event.key === 'Escape'

        handleNodeClick(
          node,
          multiSelectionActive.value,
          addSelectedNodes,
          removeSelectedNodes,
          nodesSelectionActive,
          unselect,
          nodeElement.value
        )
      } else if (
        isDraggable.value &&
        node.selected &&
        arrowKeyDiffs[event.key]
      ) {
        // prevent page scrolling
        event.preventDefault()

        ariaLiveMessage.value = `Moved selected node ${event.key
          .replace('Arrow', '')
          .toLowerCase()}. New position, x: ${~~node.position.x}, y: ${~~node
          .position.y}`

        updateNodePositions(
          {
            x: arrowKeyDiffs[event.key].x,
            y: arrowKeyDiffs[event.key].y,
          },
          event.shiftKey
        )
      }
    }
  },
})

export default NodeWrapper
