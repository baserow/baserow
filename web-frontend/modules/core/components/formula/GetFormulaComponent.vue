<template>
  <NodeViewWrapper
    as="span"
    class="get-formula-component"
    :class="{
      'get-formula-component--error': isInvalid,
      'get-formula-component--selected': isSelected,
      [`get-formula-component--compact-${compactLevel}`]: compactLevel > 0,
    }"
  >
    <span
      ref="content"
      v-tooltip="tooltip"
      tooltip-position="top"
      class="get-formula-component__content"
      @click.stop="emitToEditor('data-node-clicked', node)"
    >
      <span
        v-if="chip.source"
        ref="source"
        class="get-formula-component__source"
        :style="sourceStyle"
      >
        <i
          v-if="chip.source.icon"
          class="get-formula-component__source-icon"
          :class="chip.source.icon"
        ></i>
        <span class="get-formula-component__source-name">{{
          chip.source.name
        }}</span>
      </span>
      <span
        v-if="stepsFolded"
        class="get-formula-component__step"
        :aria-label="foldedStepsLabel"
        >…<i class="get-formula-component__caret iconoir-nav-arrow-right"></i
      ></span>
      <template v-for="(step, index) in shownSteps" v-else :key="index">
        <span v-if="step.isIndex" class="get-formula-component__index">{{
          step.name
        }}</span>
        <span v-else class="get-formula-component__step"
          >{{ step.name
          }}<i class="get-formula-component__caret iconoir-nav-arrow-right"></i
        ></span>
      </template>
      <span
        class="get-formula-component__leaf"
        :class="{ 'get-formula-component__index': chip.leaf.isIndex }"
        >{{ chip.leaf.name }}</span
      >
      <a
        class="get-formula-component__remove"
        :aria-label="$t('getExpressionComponent.remove')"
        @click.stop="deleteNode"
      >
        <i class="iconoir-cancel"></i>
      </a>
    </span>
  </NodeViewWrapper>
</template>

<script>
import { NodeViewWrapper } from '@tiptap/vue-3'
import formulaComponent from '@baserow/modules/core/mixins/formulaComponent'
import _ from 'lodash'

// The narrowest the source's badge is cut down to before the chip is
// shortened further, in px: its icon and a few letters.
const SOURCE_MIN_WIDTH = 72

export default {
  name: 'GetFormulaComponent',
  components: {
    NodeViewWrapper,
  },
  mixins: [formulaComponent],
  inject: ['nodesHierarchy'],
  data() {
    return {
      // How much the chip is shortened to fit on one line: 0 shows it all, 1
      // cuts the source's name down to a few letters, 2 also folds the steps
      // before the data into "…", 3 also cuts off the data's name.
      compactLevel: 0,
      // The narrowest the source can be cut down to, in px.
      sourceMinWidth: 0,
    }
  },
  computed: {
    stepsFolded() {
      return this.compactLevel >= 2 && this.chip.steps.length > 0
    },
    sourceStyle() {
      return this.compactLevel >= 1
        ? { flex: '0 1 auto', minWidth: `${this.sourceMinWidth}px` }
        : null
    },
    shownSteps() {
      return this.stepsFolded ? [] : this.chip.steps
    },
    foldedStepsLabel() {
      return this.chip.steps.map((step) => step.name).join(' › ')
    },
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
    /**
     * Walks the path through the data explorer's nodes, so each part has the
     * name shown in the explorer, its node (for the icon) and whether it's a
     * list index.
     */
    resolvedParts() {
      const allRootNodes = this.nodesHierarchy.flatMap(
        (category) => category.nodes || []
      )

      let currentLevelNodes = allRootNodes
      let lastNode = null
      const parts = []

      for (const identifier of this.rawPathParts) {
        let nodeFound = null
        if (currentLevelNodes) {
          nodeFound = currentLevelNodes.find(
            (node) => (node.identifier || node.name) === identifier
          )
        }

        if (nodeFound) {
          parts.push({ name: nodeFound.name, node: nodeFound, isIndex: false })
          currentLevelNodes = nodeFound.nodes
          lastNode = nodeFound
        } else if (
          lastNode &&
          lastNode.type === 'array' &&
          (/^\d+$/.test(identifier) || identifier === '*')
        ) {
          parts.push({
            name:
              identifier === '*'
                ? this.$t('common.all')
                : `#${parseInt(identifier, 10) + 1}`,
            node: null,
            isIndex: true,
          })
        } else {
          parts.push({ name: identifier, node: null, isIndex: false })
          currentLevelNodes = null
        }
      }
      return parts
    },
    /**
     * What the chip shows: the source as a badge, the steps in between, and
     * the data itself. In a deeper path the first part, like "Previous node"
     * or "Data source", is left out, as the source after it (a node or a data
     * source) says enough. The tooltip still shows the full path.
     */
    chip() {
      const parts = this.resolvedParts
      if (parts.length === 0) {
        return { source: null, steps: [], leaf: { name: '', isIndex: false } }
      }
      const leaf = parts[parts.length - 1]
      if (parts.length === 1) {
        return { source: null, steps: [], leaf }
      }
      // A provider that is itself the source, like the current record of a
      // repeat or a table, shows its own short name instead of its first part.
      const providerNode = parts[0].node
      if (providerNode?.chipSourceName) {
        return {
          source: {
            name: providerNode.chipSourceName,
            icon: providerNode.sourceIcon || null,
          },
          steps: parts.slice(1, -1),
          leaf,
        }
      }
      const sourceIndex = parts.length === 2 ? 0 : 1
      const source = parts[sourceIndex]
      return {
        source: { name: source.name, icon: source.node?.sourceIcon || null },
        steps: parts.slice(sourceIndex + 1, -1),
        leaf,
      }
    },
    fullPath() {
      return this.resolvedParts.map((part) => part.name).join(' › ')
    },
    fitKey() {
      return JSON.stringify(this.chip)
    },
    tooltip() {
      return this.isInvalid
        ? this.$t('getExpressionComponent.errorTooltip')
        : this.fullPath
    },
  },
  watch: {
    fitKey() {
      this.scheduleFit()
    },
  },
  mounted() {
    this.scheduleFit()
  },
  beforeUnmount() {
    this.resizeObserver?.disconnect()
    cancelAnimationFrame(this.fitFrame)
  },
  methods: {
    scheduleFit() {
      cancelAnimationFrame(this.fitFrame)
      this.fitFrame = requestAnimationFrame(() => {
        this.observeEditor()
        this.fit()
      })
    },
    /**
     * The chip's room changes with the editor's width, e.g. when the sidebar or
     * the field is resized, so it's fitted again then. The node view is only in
     * the editor once it's rendered, so the editor is found the first time the
     * chip is fitted.
     */
    observeEditor() {
      if (this.resizeObserver || typeof ResizeObserver === 'undefined') {
        return
      }
      const editor = this.$el?.closest?.('.ProseMirror')
      if (!editor) {
        return
      }
      this.resizeObserver = new ResizeObserver(() => this.scheduleFit())
      this.resizeObserver.observe(editor)
    },
    /**
     * Keeps the chip on one line by shortening it one step at a time, until it
     * stops overflowing. Every chip keeps its source and its data, so they all
     * have the same shape. The full path stays in the tooltip.
     */
    async fit() {
      for (let level = 0; level <= 3; level++) {
        if (level === 1) {
          // A few letters of the source, or all of it when it's that short.
          this.sourceMinWidth = Math.min(
            SOURCE_MIN_WIDTH,
            this.$refs.source?.offsetWidth ?? 0
          )
        }
        if (level === 2 && this.chip.steps.length === 0) {
          continue
        }
        this.compactLevel = level
        await this.$nextTick()
        const content = this.$refs.content
        if (!content || content.scrollWidth <= content.clientWidth) {
          return
        }
      }
    },
  },
}
</script>
