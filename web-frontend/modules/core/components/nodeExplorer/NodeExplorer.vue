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
          @update:selected-index="resetSearch"
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
              @example-click="$emit('example-click', $event)"
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
            @example-click="$emit('example-click', $event)"
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
    /**
     * A formula node to reveal: its tab is opened and the explorer scrolls to
     * it. Either `{ type: 'function', name }`, `{ type: 'operator', name }`
     * with the operator symbol as name, or `{ type: 'data', path }`.
     */
    revealNode: {
      type: Object,
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
      type: String,
      required: false,
      default: 'none',
      validator: (value) => ['none', 'all', 'array', 'object'].includes(value),
    },
  },
  emits: ['node-selected', 'node-toggled', 'node-unselected', 'example-click'],
  data() {
    return {
      activeTabIndex: 0,
      search: null,
      debounceSearch: null,
      debouncedSearch: null,
      // A map of open node paths
      openNodes: new Set(),
      // Set when the search is cleared to reveal a node, so that clearing it
      // doesn't unselect the data node being revealed.
      skipSearchUnselect: false,
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
      if (this.skipSearchUnselect) {
        this.skipSearchUnselect = false
      } else {
        this.$emit('node-unselected')
      }
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
    revealNode: {
      handler(target) {
        if (target) {
          this.reveal(target)
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
    /**
     * Finds the tab and the path of the node to reveal in the explorer.
     * @param {Object} target the node to reveal, see the `revealNode` prop.
     * @returns {Object|null} the `{ tabIndex, path }`, or null if the explorer
     *   doesn't have the node.
     */
    findRevealLocation(target) {
      const tabs = this.filteredNodesHierarchy
      const nodeKey = (node) => node.identifier || node.name

      if (target.type === 'data') {
        const [rootKey] = _.toPath(target.path)
        const tabIndex = tabs.findIndex(
          (tab) =>
            tab.type === 'data' &&
            (tab.nodes || []).some((node) => nodeKey(node) === rootKey)
        )
        return tabIndex === -1 ? null : { tabIndex, path: target.path }
      }

      const isMatch = (node) =>
        node.type === target.type &&
        !node.nodes &&
        (target.type === 'operator'
          ? node.signature?.operator === target.name
          : node.name.toLowerCase() === target.name.toLowerCase())

      const findPath = (nodes, parentPath = []) => {
        for (const node of nodes || []) {
          const nodePath = [...parentPath, nodeKey(node)]
          if (isMatch(node)) {
            return nodePath.join('.')
          }
          const subPath = findPath(node.nodes, nodePath)
          if (subPath) {
            return subPath
          }
        }
        return null
      }

      for (const [tabIndex, tab] of tabs.entries()) {
        if (tab.type === target.type) {
          const path = findPath(tab.nodes)
          if (path) {
            return { tabIndex, path }
          }
        }
      }
      return null
    },
    /**
     * Opens the tab of the given node, clears the search, expands the node's
     * parents and scrolls to it.
     * @param {Object} target the node to reveal, see the `revealNode` prop.
     */
    reveal(target) {
      const location = this.findRevealLocation(target)
      if (!location) {
        return
      }
      if (this.search) {
        this.skipSearchUnselect = true
      }
      this.resetSearch(location.tabIndex)
      // Switching tab resets the open nodes, so we expand them afterwards.
      this.$nextTick(() => {
        this.toggleNode(location.path, true)
        this.$nextTick(() => this.scrollToPath(location.path))
      })
    },
    /**
     * Scrolls to the row of the given path and briefly highlights it. The
     * explorer and its tab may not be rendered or visible yet when they were
     * just opened by the same click, so we retry for a few frames. After that
     * we fall back to the closest rendered parent, e.g. for an array item
     * beyond the ones shown.
     * @param {String} path the path of the node to scroll to.
     * @param {Number} retries how many more frames to wait for the row.
     */
    scrollToPath(path, retries = 10) {
      const rows = Array.from(
        this.$refs.wrapper?.querySelectorAll('[data-node-path]') || []
      )
      const row = this.getPathAndParents(path)
        .reverse()
        .map((candidate) =>
          rows.find((row) => row.dataset.nodePath === candidate)
        )
        .find(Boolean)

      const isReady =
        row?.dataset.nodePath === path && row.getClientRects().length > 0
      if (!isReady && retries > 0) {
        requestAnimationFrame(() => this.scrollToPath(path, retries - 1))
        return
      }
      if (!row) {
        return
      }
      row.scrollIntoView({ block: 'nearest' })
      row.classList.remove('node-explorer-content__content--revealed')
      // Force a reflow so the highlight animation restarts on repeat reveals.
      void row.offsetWidth
      row.classList.add('node-explorer-content__content--revealed')
    },
  },
}
</script>
