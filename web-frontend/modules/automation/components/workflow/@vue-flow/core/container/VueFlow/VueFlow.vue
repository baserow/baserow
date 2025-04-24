<script>
import { useVModel } from '@vueuse/core'
import { onUnmounted, provide, defineComponent } from 'vue'
import Viewport from '../Viewport/Viewport.vue'
import A11yDescriptions from '../../components/A11y/A11yDescriptions.vue'
import { Slots } from '../../context'
import { useOnInitHandler } from '../../composables/useOnInitHandler.js'
import { useWatchProps } from '../../composables/useWatchProps.js'
import { useVueFlow } from '../../composables/useVueFlow.js'
import { useHooks } from '../../store/hooks'
import EdgeRenderer from '../EdgeRenderer/EdgeRenderer.vue'
import NodeRenderer from '../NodeRenderer/NodeRenderer.vue'
import { useStylesLoadedWarning } from '../../composables/useStylesLoadedWarning.js'

export default defineComponent({
  name: 'VueFlow',
  components: {
    Viewport,
    EdgeRenderer,
    NodeRenderer,
    A11yDescriptions,
  },
  props: {
    modelValue: {},
    nodes: {},
    edges: {},
    snapToGrid: { default: undefined },
    onlyRenderVisibleElements: { default: undefined },
    edgesUpdatable: { default: undefined },
    nodesConnectable: { default: undefined },
    nodesDraggable: { default: undefined },
    elementsSelectable: { default: undefined },
    selectNodesOnDrag: { default: undefined },
    preventScrolling: { default: undefined },
    zoomOnScroll: { default: undefined },
    zoomOnPinch: { default: undefined },
    zoomOnDoubleClick: { default: undefined },
    panOnScroll: { default: undefined },
    panOnDrag: { default: undefined },
    applyDefault: { default: undefined },
    fitViewOnInit: { default: undefined },
    connectOnClick: { default: undefined },
    connectionLineStyle: { default: undefined },
    connectionLineOptions: { default: undefined },
    autoConnect: { default: undefined },
    elevateEdgesOnSelect: { default: undefined },
    elevateNodesOnSelect: { default: undefined },
    disableKeyboardA11y: { default: undefined },
    edgesFocusable: { default: undefined },
    nodesFocusable: { default: undefined },
    autoPanOnConnect: { default: undefined },
    autoPanOnNodeDrag: { default: undefined },
    isValidConnection: { default: undefined },
    deleteKeyCode: { default: undefined },
    selectionKeyCode: { default: undefined },
    multiSelectionKeyCode: { default: undefined },
    panActivationKeyCode: { default: undefined },
    zoomActivationKeyCode: { default: undefined },
  },
  setup(props, { emit, slots }) {
    const modelValue = useVModel(props, 'modelValue', emit)
    const modelNodes = useVModel(props, 'nodes', emit)
    const modelEdges = useVModel(props, 'edges', emit)

    const flowInstance = useVueFlow(props)

    // watch props and update store state
    const dispose = useWatchProps(
      { modelValue, nodes: modelNodes, edges: modelEdges },
      props,
      flowInstance
    )

    useHooks(emit, flowInstance.hooks)

    useOnInitHandler()

    useStylesLoadedWarning()

    // slots will be passed via provide
    // this is to avoid having to pass them down through all the components
    // as that would require a lot of boilerplate and causes significant performance drops
    provide(Slots, slots)

    onUnmounted(() => {
      // clean up watcher scope
      dispose()
    })

    return {
      flowInstance,
    }
  },
})
</script>

<template>
  <div :ref="flowInstance.vueFlowRef" class="vue-flow">
    <Viewport>
      <EdgeRenderer />

      <div class="vue-flow__edge-labels" />

      <NodeRenderer />

      <!-- This slot is affected by zooming & panning -->
      <slot name="zoom-pane" />
    </Viewport>

    <!-- This slot is _not_ affected by zooming & panning -->
    <slot />
    <!-- 
    <A11yDescriptions /> -->
  </div>
</template>
