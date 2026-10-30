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
      v-tooltip="$t('getExpressionComponent.errorTooltip')"
      tooltip-position="top"
      :hide-tooltip="!isInvalid"
      @click.stop="emitToEditor('data-node-clicked', node)"
    >
      <template v-for="(part, index) in pathParts" :key="index">
        <i
          v-if="index > 0"
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
import { NodeViewWrapper } from '@tiptap/vue-3'
import formulaComponent from '@baserow/modules/core/mixins/formulaComponent'
import _ from 'lodash'

export default {
  name: 'GetFormulaComponent',
  components: {
    NodeViewWrapper,
  },
  mixins: [formulaComponent],
  inject: {
    nodesHierarchy: {},
    parseFormulaPath: { default: () => _.toPath },
  },
  computed: {
    isInvalid() {
      return this.resolvedPath.some((part) => !part.valid)
    },
    path() {
      return this.node.attrs.path
    },
    isSelected() {
      return this.node.attrs.isSelected
    },
    rawPathParts() {
      return this.parseFormulaPath(this.path)
    },
    pathParts() {
      return this.resolvedPath.map((part) => part.name)
    },
    resolvedPath() {
      const allRootNodes = this.nodesHierarchy.flatMap(
        (category) => category.nodes || []
      )

      let currentLevelNodes = allRootNodes
      let lastNode = null

      return this.rawPathParts.map((identifier) => {
        const nodeFound =
          currentLevelNodes?.find(
            (node) => (node.identifier || node.name) === identifier
          ) || lastNode?.getChildNode?.(identifier)

        if (nodeFound) {
          currentLevelNodes = nodeFound.nodes
          lastNode = nodeFound
          return { name: nodeFound.name, valid: true }
        } else if (
          lastNode &&
          lastNode.type === 'array' &&
          (/^\d+$/.test(identifier) || identifier === '*')
        ) {
          currentLevelNodes = lastNode.nodes
          return {
            name:
              identifier === '*' ? `[${this.$t('common.all')}]` : identifier,
            valid: true,
          }
        }
        currentLevelNodes = null
        lastNode = null
        return { name: identifier, valid: false }
      })
    },
  },
}
</script>
