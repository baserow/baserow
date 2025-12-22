<template>
  <div class="node-explorer">
    <div ref="wrapper">
      <div v-if="loading" class="context--loading">
        <div class="loading" />
      </div>
      <template v-else>
        <Tabs
          v-if="filteredNodesHierarchy.length > 1"
          :selected-index="activeTabIndex"
          content-no-padding
          rounded
          full-height
          @update:selectedIndex="resetSearch"
        >
          <Tab
            v-for="hierarchyNode in filteredNodesHierarchy"
            :key="hierarchyNode.name"
            :title="hierarchyNode.name"
          >
            <NodeExplorerTab
              v-model="search"
              :hierarchy-node="hierarchyNode"
              :empty-results="emptyResults"
              :open-nodes="openNodes"
              :node-selected="nodeSelected"
              :debounced-search="debouncedSearch"
              :allow-node-selection="allowNodeSelection"
              @reset-search="resetSearch"
              @node-selected="$emit('node-selected', $event)"
              @toggle="toggleNode"
            />
          </Tab>
        </Tabs>
        <template v-else-if="filteredNodesHierarchy.length === 1">
          <NodeExplorerTab
            v-model="search"
            :hierarchy-node="filteredNodesHierarchy[0]"
            :empty-results="emptyResults"
            :open-nodes="openNodes"
            :node-selected="nodeSelected"
            :debounced-search="debouncedSearch"
            :allow-node-selection="allowNodeSelection"
            @reset-search="resetSearch"
            @node-selected="$emit('node-selected', $event)"
            @toggle="toggleNode"
          />
        </template>
      </template>
    </div>
  </div>
</template>

<script>
import NodeExplorerTab from '@baserow/modules/core/components/nodeExplorer/NodeExplorerTab'

import _ from 'lodash'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

export default {
  name: 'NodeExplorer',
  components: {
    NodeExplorerTab,
  },
  provide() {
    return {
      getFormulaMode: () => this.mode,
    }
  },
  props: {
    mode: {
      type: String,
      required: false,
      default: 'advanced',
      validator: (value) => BASEROW_FORMULA_MODES.includes(value),
    },
    nodeSelected: {
      type: String,
      required: false,
      default: null,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    nodesHierarchy: {
      type: Array,
      required: false,
      default: () => [],
    },
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      activeTabIndex: 0,
      search: null,
      debounceSearch: null,
      debouncedSearch: null,
      // A map of open node paths
      openNodes: new Set(),
    }
  },
  computed: {
    filteredNodesHierarchy() {
      if (this.mode === 'simple') {
        return this.nodesHierarchy.filter(
          (hierarchyNode) => hierarchyNode.type === 'data'
        )
      }
      return this.nodesHierarchy
    },
    isSearching() {
      return Boolean(this.debouncedSearch)
    },
    emptyResults() {
      return this.isSearching && this.openNodes.size === 0
    },
    matchingPaths() {
      if (!this.isSearching) {
        return new Set()
      } else {
        // Get the nodes from the current tab
        const currentTab = this.filteredNodesHierarchy[this.activeTabIndex]
        if (!currentTab || !currentTab.nodes) {
          return new Set()
        }
        return this.matchesSearch(currentTab.nodes, this.debouncedSearch)
      }
    },
  },
  watch: {
    mode(newMode, oldMode) {
      if (newMode !== oldMode) {
        this.activeTabIndex = 0
        this.resetSearch()
      }
    },
    /**
     * Debounces the actual search to prevent perf issues
     */
    search(newSearch) {
      this.$emit('node-unselected')
      clearTimeout(this.debounceSearch)
      this.debounceSearch = setTimeout(() => {
        this.debouncedSearch = newSearch ? newSearch.trim().toLowerCase() : null
      }, 300)
    },
    matchingPaths(value) {
      this.openNodes = value
    },
    nodeSelected: {
      handler(path) {
        if (path) {
          this.debouncedSearch = null
          this.toggleNode(path, true)
        }
      },
      immediate: true,
    },
  },
  mounted() {
    this.onShow()
  },
  methods: {
    resetSearch(newTabIndex) {
      this.search = null
      this.debouncedSearch = null
      this.openNodes = new Set()
      if (typeof newTabIndex === 'number') {
        this.activeTabIndex = newTabIndex
      }
    },
    onShow() {
      this.search = null
      this.openNodes = new Set()
    },
    /**
     * Given a dotted path, returns a list of prefixes and the given path.
     * @param {String} path the path we want the ancestors for.
     */
    getPathAndParents(path) {
      return _.toPath(path).map((item, index, pathParts) =>
        pathParts.slice(0, index + 1).join('.')
      )
    },
    /**
     * Returns a Set of leaf nodes path that match the search term (and their parents).
     * @param {Array} nodes Nodes tree.
     * @param {String} parentPath Path of the current nodes.
     * @returns A Set of path of nodes that match the search term
     */
    matchesSearch(nodes, search, parentPath = []) {
      return (nodes || []).reduce((acc, subNode) => {
        // Use identifier if available, otherwise use name
        const nodeKey = subNode.identifier || subNode.name
        let subNodePath = [...parentPath, nodeKey]

        // Check if this node's name matches the search
        const nodeNameSanitised = subNode.name.trim().toLowerCase()
        const nodeMatches = nodeNameSanitised.includes(search)

        if (subNode.nodes) {
          // It's not a leaf
          if (subNode.type === 'array') {
            // For array we have a special case. We need to match any intermediate value
            // Can be either `*` or an integer. We use the `__any__` placeholder to
            // achieve that.
            subNodePath = [...parentPath, nodeKey, '__any__']
          }

          // If this node matches, add it and its parents
          if (nodeMatches) {
            const pathsToAdd = this.getPathAndParents(subNodePath.join('.'))
            acc = new Set([...acc, ...pathsToAdd])
          }

          // Also search in child nodes
          const subSubNodes = this.matchesSearch(
            subNode.nodes,
            search,
            subNodePath
          )
          acc = new Set([...acc, ...subSubNodes])
        } else if (nodeMatches) {
          // It's a leaf and the name matches the search
          // We also add the parents of the node
          const pathsToAdd = this.getPathAndParents(subNodePath.join('.'))
          acc = new Set([...acc, ...pathsToAdd])
        }
        return acc
      }, new Set())
    },
    /**
     * Toggles a node state
     * @param {string} path to open/close.
     * @param {Boolean} forceOpen if we want to open the node anyway.
     */
    toggleNode(path, forceOpen = false) {
      const shouldOpenNode = forceOpen || !this.openNodes.has(path)

      if (shouldOpenNode) {
        // Open all parents as well
        this.openNodes = new Set([
          ...this.openNodes,
          ...this.getPathAndParents(path),
        ])
      } else {
        const newOpenNodes = new Set(this.openNodes)
        newOpenNodes.delete(path)
        this.openNodes = newOpenNodes
      }

      this.$emit('node-toggled')
    },
  },
}
</script>
