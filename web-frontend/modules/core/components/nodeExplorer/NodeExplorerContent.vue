<template>
  <div
    v-if="shouldShow"
    class="node-explorer-content"
    :class="{
      [`node-explorer-content--level-${depth}`]: true,
      'node-explorer-content--selected': isSelected,
    }"
  >
    <div
      class="node-explorer-content__content"
      @click="handleClick(node)"
      @mouseenter="onNodeHover($event, node)"
      @mouseleave="onNodeLeave"
    >
      <span v-if="depth > 0" class="node-explorer-content__icon">
        <i class="node-explorer-content__content-icon" :class="getIcon(node)" />
      </span>
      <span class="node-explorer-content__name">{{ node.name }}</span>
      <span v-if="isSelected" class="node-explorer-content__selected-icon">
        <i class="iconoir-check-circle" />
      </span>
      <span
        v-else-if="allowArraySelection(node)"
        class="data-explorer-node__select-node"
        @click.stop="handleClick(node, true)"
      >
        {{ $t('dataExplorerNode.selectNode') }}
      </span>
      <NodeHelpTooltip ref="nodeHelpTooltip" :node="node" />
    </div>
    <div v-if="hasChildren && isOpen" class="node-explorer-content__children">
      <template v-if="node.type !== 'array'">
        <NodeExplorerContent
          v-for="child in node.nodes"
          :key="child.name"
          :node="child"
          :depth="depth + 1"
          :open-nodes="openNodes"
          :path="
            path
              ? `${path}.${child.identifier || child.name}`
              : child.identifier || child.name
          "
          :search-path="`${searchPath ? searchPath + '.' : ''}${
            child.identifier || child.name
          }`"
          :node-selected="nodeSelected"
          :allow-node-selection="allowNodeSelection"
          :search="search"
          @click="$emit('click', $event)"
          @toggle="$emit('toggle', $event)"
        />
      </template>
      <div v-else>
        <NodeExplorerContent
          v-for="subNode in arrayNodes"
          :key="subNode.identifier"
          :node="subNode"
          :depth="depth + 1"
          :open-nodes="openNodes"
          :node-selected="nodeSelected"
          :search="search"
          :path="`${path}.${subNode.identifier}`"
          :allow-node-selection="allowNodeSelection"
          :search-path="`${searchPath}.__any__`"
          @click="$emit('click', $event)"
          @toggle="$emit('toggle', $event)"
        />
        <button
          v-tooltip="$t('dataExplorerNode.showMore')"
          class="node-explorer-content__array-node-more"
          @click="count += nextIncrement"
        >
          {{ `[ ${count}...${nextCount - 1} ]` }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import NodeHelpTooltip from '@baserow/modules/core/components/nodeExplorer/NodeHelpTooltip.vue'
export default {
  name: 'NodeExplorerContent',
  components: {
    NodeHelpTooltip,
  },
  inject: ['getFormulaMode'],
  props: {
    node: {
      type: Object,
      required: true,
    },
    openNodes: {
      type: Set,
      required: true,
    },
    path: {
      type: [String, null],
      required: false,
      default: null,
    },
    searchPath: {
      type: String,
      required: true,
    },
    nodeSelected: {
      type: String,
      required: false,
      default: null,
    },
    search: {
      type: String,
      required: false,
      default: null,
    },
    depth: {
      type: Number,
      required: false,
      default: 0,
    },
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return { count: 3, tooltipTimer: null }
  },
  computed: {
    hasChildren() {
      const children = this.node.nodes
      return children && children.length > 0
    },
    sortedNodes() {
      if (this.hasChildren) {
        return [...this.node.nodes].sort((a, b) => a.order - b.order)
      } else {
        return []
      }
    },
    isOpen() {
      return (
        // It's open if we are the first level
        this.depth === 0 ||
        // if it's in open node
        this.openNodes.has(this.path) ||
        // or if the search path is in openNodes
        // The search path is the version with `__any__` instead of array indexes
        this.openNodes.has(this.searchPath)
      )
    },
    isSelected() {
      return this.nodeSelected === this.path
    },
    shouldShow() {
      if (!this.search) return true
      return this.openNodes.has(this.searchPath)
    },
    nextCount() {
      return this.count + 10 - ((this.count + 10) % 10)
    },
    nextIncrement() {
      return this.nextCount - this.count
    },
    arrayNodes() {
      if (this.node.type === 'array') {
        // In case of array node, we generate the nodes on demand
        const head = {
          nodes: this.node.nodes,
          identifier: '*',
          name: `[${this.$t('common.all')}]`,
        }
        return [
          head,
          ...[...Array(this.count).keys()].map((index) => ({
            nodes: this.node.nodes,
            identifier: `${index}`,
            name: `${index}`,
          })),
        ]
      }
      return []
    },
  },
  methods: {
    allowArraySelection(node) {
      return (
        node.type === 'array' &&
        (this.allowNodeSelection || this.getFormulaMode() === 'advanced')
      )
    },
    handleClick(node, isNode) {
      if (this.depth < 1) {
        // We don't want to click on first level
        return
      }
      if (this.hasChildren && !isNode) {
        if (this.search === null && this.path) {
          this.$emit('toggle', this.path)
        }
      } else {
        this.$emit('click', { path: this.path, node })
      }
    },
    getIcon(node) {
      if (this.hasChildren) {
        return this.isOpen
          ? 'iconoir-nav-arrow-down'
          : 'iconoir-nav-arrow-right'
      }
      return node.icon
    },
    onNodeHover($event, node) {
      if (this.tooltipTimer) {
        clearTimeout(this.tooltipTimer)
      }

      if (
        (node.type === 'function' || node.type === 'operator') &&
        node.example &&
        node.description
      ) {
        this.tooltipTimer = setTimeout(() => {
          if (this.$refs.nodeHelpTooltip) {
            this.$refs.nodeHelpTooltip.show(
              $event.target,
              'bottom',
              'right',
              5,
              10
            )
          }
        }, 300)
      }
    },
    onNodeLeave() {
      if (this.tooltipTimer) {
        clearTimeout(this.tooltipTimer)
        this.tooltipTimer = null
      }

      this.hideTooltip()
    },
    hideTooltip() {
      if (this.$refs.nodeHelpTooltip) {
        this.$refs.nodeHelpTooltip.hide()
      }
    },
  },
}
</script>
