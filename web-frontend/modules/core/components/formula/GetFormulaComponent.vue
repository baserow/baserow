<template>
  <NodeViewWrapper
    as="span"
    class="get-formula-component"
    :class="{
      'get-formula-component--error': isInvalid,
      'get-formula-component--selected': isSelected,
    }"
  >
    <div
      v-tooltip="$t('getFormulaComponent.errorTooltip')"
      tooltip-position="top"
      :hide-tooltip="!isInvalid"
      @click="emitToEditor('data-component-clicked', node)"
    >
      <template v-for="(part, index) in pathParts">
        <i
          v-if="index > 0"
          :key="index"
          class="get-formula-component__caret iconoir-nav-arrow-right"
        />

        {{ part }}
      </template>
      <a class="get-formula-component__remove" @click.stop="deleteNode">
        <i class="iconoir-cancel"></i>
      </a>
    </div>
  </NodeViewWrapper>
</template>

<script>
import { NodeViewWrapper } from '@tiptap/vue-2'
import formulaComponent from '@baserow/modules/core/mixins/formulaComponent'
import _ from 'lodash'

export default {
  name: 'GetFormulaComponent',
  components: {
    NodeViewWrapper,
  },
  mixins: [formulaComponent],
  inject: ['applicationContext', 'dataProviders'],
  computed: {
    isInvalid() {
      return this.findNode(this.nodes, _.toPath(this.path)) === null
    },
    path() {
      return this.node.attrs.path
    },
    isSelected() {
      return this.node.attrs.isSelected
    },
    rawPathParts() {
      return _.toPath(this.path)
    },
    dataProviderType() {
      const pathParts = this.rawPathParts
      return this.dataProviders.find(
        (dataProvider) => dataProvider.type === pathParts[0]
      )
    },
    nodes() {
      return [this.dataProviderType.getNodes(this.applicationContext)]
    },
    pathParts() {
      const translatedPathPart = this.rawPathParts.map((_, index) =>
        this.dataProviderType.getPathTitle(
          this.applicationContext,
          this.rawPathParts.slice(0, index + 1)
        )
      )

      translatedPathPart[0] = this.dataProviderType.name
      return translatedPathPart
    },
  },
  methods: {
    findNode(nodes, path) {
      const [identifier, ...rest] = path

      if (!nodes) {
        return null
      }

      const nodeFound = nodes.find((node) => node.identifier === identifier)

      if (!nodeFound) {
        return null
      }

      if (rest.length > 0) {
        if (nodeFound.type === 'array') {
          const [index, ...afterIndex] = rest
          // Check that the index is what is expected
          if (!(index === '*' || /^\d+$/.test(index))) {
            return null
          }
          return this.findNode(nodeFound.nodes, afterIndex)
        } else {
          return this.findNode(nodeFound.nodes, rest)
        }
      }

      return nodeFound
    },
  },
}
</script>
