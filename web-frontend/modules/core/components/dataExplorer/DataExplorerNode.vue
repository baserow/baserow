<template>
  <div
    v-if="showNode"
    class="data-explorer-node"
    :class="{
      [`data-explorer-node--level-${depth}`]: true,
      'data-explorer-node--selected': isSelected,
    }"
  >
    <div class="data-explorer-node__content" @click="handleClick(node)">
      <i
        v-if="depth > 0"
        class="data-explorer-node__content-icon"
        :class="getIcon(node)"
      />
      <span class="data-explorer-node__content-name">{{ node.name }}</span>
      <i
        v-if="isSelected"
        class="data-explorer-node__content-selected-icon iconoir-check-circle"
      />
      <span
        v-else-if="allowNodeSelection && node.type === 'array'"
        class="data-explorer-node__select-node"
        @click.stop="handleClick(node, true)"
      >
        {{ $t('dataExplorerNode.selectNode') }}
      </span>
    </div>
    <div v-if="isNodeOpen" ref="nodes" class="data-explorer-node__children">
      <template v-if="node.type !== 'array'">
        <DataExplorerNode
          v-for="subNode in sortedNodes"
          :key="subNode.identifier"
          :node="subNode"
          :depth="depth + 1"
          :open-nodes="openNodes"
          :node-selected="nodeSelected"
          :path="subNode.identifier ? `${path}.${subNode.identifier}` : path"
          :search-path="
            subNode.identifier
              ? `${searchPath}.${subNode.identifier}`
              : searchPath
          "
          :search="search"
          :allow-node-selection="allowNodeSelection"
          @click="$emit('click', $event)"
          @toggle="$emit('toggle', $event)"
        />
      </template>
      <div v-else>
        <DataExplorerNode
          v-for="subNode in arrayNodes"
          :key="subNode.identifier"
          :node="subNode"
          :depth="depth + 1"
          :open-nodes="openNodes"
          :node-selected="nodeSelected"
          :allow-node-selection="allowNodeSelection"
          :search="search"
          :path="`${path}.${subNode.identifier}`"
          :search-path="`${searchPath}.__any__`"
          @click="$emit('click', $event)"
          @toggle="$emit('toggle', $event)"
        />
        <button
          v-tooltip="$t('dataExplorerNode.showMore')"
          class="data-explorer-node__array-node-more"
          @click="count += nextIncrement"
        >
          {{ `[ ${count}...${nextCount - 1} ]` }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'

export default {
  name: 'DataExplorerNode',
  props: {
    node: {
      type: Object,
      required: true,
    },
    depth: {
      type: Number,
      required: false,
      default: 0,
    },
    openNodes: {
      type: Set,
      required: true,
    },
    path: {
      type: String,
      required: true,
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
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return { count: 3 }
  },
  computed: {
    isSelected() {
      return this.nodeSelected === this.path
    },
    showNode() {
      // we show the node if...
      return (
        // We are not searching
        this.search === null ||
        // It is selected
        this.isSelected ||
        // It has children and at least one children matches
        (this.hasChildren && this.openNodes.has(this.searchPath)) ||
        // Or it's a leaf and it matches the search term
        this.node.name.trim().toLowerCase().includes(this.search)
      )
    },
    hasChildren() {
      return this.node.nodes?.length > 0
    },
    sortedNodes() {
      if (this.hasChildren) {
        return [...this.node.nodes].sort((a, b) => a.order - b.order)
      } else {
        return []
      }
    },
    isNodeOpen() {
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
  watch: {
    nodeSelected: {
      handler(newValue) {
        // Generate enough array nodes to display arbitrary selected data
        if (this.node.type === 'array' && newValue?.startsWith(this.path)) {
          const nodeSelectedPath = _.toPath(newValue)
          const pathParts = _.toPath(this.path)
          const indexStr = nodeSelectedPath[pathParts.length]

          if (indexStr !== '*') {
            const index = parseInt(indexStr)
            if (this.count <= index) {
              this.count = index + 10 - ((index + 10) % 10)
            }
          }
        }
      },
      immediate: true,
    },
    isSelected: {
      async handler(newValue) {
        if (newValue) {
          await this.$nextTick()
          // We scroll it into view when it becomes selected.
          this.$el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      },
      immediate: true,
    },
  },
  methods: {
    handleClick(node, isNode) {
      if (this.depth < 1) {
        // We don't want to click on first level
        return
      }
      if (this.hasChildren && !isNode) {
        if (this.search === null) {
          this.$emit('toggle', this.path)
        }
      } else {
        this.$emit('click', { path: this.path, node })
      }
    },
    getIcon(node) {
      if (this.hasChildren) {
        return this.isNodeOpen
          ? 'iconoir-nav-arrow-down'
          : 'iconoir-nav-arrow-right'
      }
      return node.icon
    },
  },
}
</script>
