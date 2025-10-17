<template>
  <Context
    overflow-scroll
    max-height-if-outside-viewport
    :hide-on-click-outside="false"
    class="data-explorer"
    @shown="onShow"
  >
    <div ref="wrapper">
      <div v-if="loading" class="context--loading">
        <div class="loading" />
      </div>
      <template v-else>
        <SelectSearch
          v-model="search"
          :placeholder="$t('action.search')"
          class="margin-bottom-1"
        />
        <DataExplorerNode
          v-for="node in nodes"
          :key="node.identifier"
          :node="node"
          :open-nodes="openNodes"
          :path="node.identifier"
          :search-path="node.identifier"
          :node-selected="nodeSelected"
          :search="debouncedSearch"
          :allow-node-selection="allowNodeSelection"
          @click="$emit('node-selected', $event)"
          @toggle="toggleNode"
        />
        <div
          v-if="nodes.length === 0 || emptyResults"
          class="context__description"
        >
          <span v-if="emptyResults">
            {{ $t('dataExplorer.noMatchingNodesText') }}
          </span>
          <span v-else>{{ $t('dataExplorer.noProvidersText') }}</span>
        </div>
      </template>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import SelectSearch from '@baserow/modules/core/components/SelectSearch'
import DataExplorerNode from '@baserow/modules/core/components/dataExplorer/DataExplorerNode'

import _ from 'lodash'

export default {
  name: 'DataExplorer',
  components: { SelectSearch, DataExplorerNode },
  mixins: [context],
  props: {
    nodes: {
      type: Array,
      required: false,
      default: () => [],
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
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      search: null,
      debounceSearch: null,
      debouncedSearch: null,
      // A map of open node paths
      openNodes: new Set(),
    }
  },
  computed: {
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
        return this.matchesSearch(this.nodes, this.debouncedSearch)
      }
    },
  },
  watch: {
    /**
     * Debounces the actual search to prevent perf issues
     */
    search(newSearch) {
      this.$emit('node-unselected')
      clearTimeout(this.debounceSearch)
      this.debounceSearch = setTimeout(() => {
        this.debouncedSearch = newSearch.trim().toLowerCase() || null
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
  methods: {
    /**
     * Resets state on show context
     */
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
        let subNodePath = [...parentPath, subNode.identifier]
        if (subNode.nodes) {
          // It's not a leaf
          if (subNode.type === 'array') {
            // For array we have a special case. We need to match any intermediate value
            // Can be either `*` or an integer. We use the `__any__` placeholder to
            // achieve that.
            subNodePath = [...parentPath, subNode.identifier, '__any__']
          }
          const subSubNodes = this.matchesSearch(
            subNode.nodes,
            search,
            subNodePath
          )
          acc = new Set([...acc, ...subSubNodes])
        } else {
          // It's a leaf we check if the name matches the search
          const nodeNameSanitised = subNode.name.trim().toLowerCase()

          if (nodeNameSanitised.includes(search)) {
            // We also add the parents of the node
            acc = new Set([...acc, ...this.getPathAndParents(subNodePath)])
          }
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
