<template>
  <div class="node-explorer-tab">
    <SelectSearch
      v-if="!hierarchyNode.empty"
      :value="search"
      :placeholder="$t('action.search')"
      @input="$emit('update:search', $event)"
      @clear="$emit('reset-search')"
    />
    <div class="node-explorer-tab__scrollable">
      <div v-if="emptyResults" class="node-explorer__content--empty">
        <span>{{ $t('nodeExplorer.noResults') }}</span>
        <Button
          size="small"
          tag="a"
          type="secondary"
          @click.stop="$emit('reset-search')"
        >
          {{ $t('nodeExplorer.resetSearch') }}
        </Button>
      </div>
      <div
        v-else-if="hierarchyNode.empty"
        class="node-explorer__content--empty"
      >
        <span>{{ hierarchyNode.emptyText }}</span>
      </div>
      <div v-else class="node-explorer__content">
        <NodeExplorerContent
          v-for="node in hierarchyNode.nodes"
          :key="node.name"
          :node="node"
          :open-nodes="openNodes"
          :path="node.identifier || node.name"
          :search-path="node.identifier || node.name"
          :node-selected="nodeSelected"
          :search="debouncedSearch"
          :allow-node-selection="allowNodeSelection"
          @click="$emit('node-selected', $event)"
          @toggle="$emit('toggle', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import SelectSearch from '@baserow/modules/core/components/SelectSearch'
import NodeExplorerContent from '@baserow/modules/core/components/nodeExplorer/NodeExplorerContent'

export default {
  name: 'NodeExplorerTab',
  components: {
    SelectSearch,
    NodeExplorerContent,
  },
  model: {
    prop: 'search',
    event: 'update:search',
  },
  props: {
    hierarchyNode: {
      type: Object,
      required: true,
    },
    search: {
      type: String,
      required: false,
      default: null,
    },
    debouncedSearch: {
      type: String,
      required: false,
      default: null,
    },
    emptyResults: {
      type: Boolean,
      required: true,
    },
    openNodes: {
      type: Set,
      required: true,
    },
    nodeSelected: {
      type: String,
      required: false,
      default: null,
    },
    allowNodeSelection: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
