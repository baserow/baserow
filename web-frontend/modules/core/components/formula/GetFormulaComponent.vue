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
  inject: ['nodesHierarchy'],
  computed: {
    isInvalid() {
      const allRootNodes = this.nodesHierarchy.flatMap(
        (category) => category.nodes || []
      )

      let currentLevelNodes = allRootNodes
      let lastNode = null

      for (const identifier of this.rawPathParts) {
        let nodeFound = null
        if (currentLevelNodes) {
          nodeFound = currentLevelNodes.find(
            (node) => (node.identifier || node.name) === identifier
          )
        }

        if (nodeFound) {
          currentLevelNodes = nodeFound.nodes
          lastNode = nodeFound
        } else if (
          lastNode &&
          lastNode.type === 'array' &&
          (/^\d+$/.test(identifier) || identifier === '*')
        ) {
          currentLevelNodes = lastNode.nodes
        } else {
          return true
        }
      }
      return false
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
    pathParts() {
      const allRootNodes = this.nodesHierarchy.flatMap(
        (category) => category.nodes || []
      )

      let currentLevelNodes = allRootNodes
      let lastNode = null
      const translatedParts = []

      for (const identifier of this.rawPathParts) {
        let nodeFound = null
        if (currentLevelNodes) {
          nodeFound = currentLevelNodes.find(
            (node) => (node.identifier || node.name) === identifier
          )
        }

        if (nodeFound) {
          translatedParts.push(nodeFound.name)
          currentLevelNodes = nodeFound.nodes
          lastNode = nodeFound
        } else if (
          lastNode &&
          lastNode.type === 'array' &&
          (/^\d+$/.test(identifier) || identifier === '*')
        ) {
          translatedParts.push(
            identifier === '*' ? `[${this.$t('common.all')}]` : identifier
          )
        } else {
          translatedParts.push(identifier)
          currentLevelNodes = null
        }
      }
      return translatedParts
    },
  },
}
</script>
