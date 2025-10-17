<template>
  <div>
    <EditorContent
      :id="forInput"
      ref="editor"
      class="form-input formula-input-field"
      role="textbox"
      :class="classes"
      :editor="editor"
      @data-node-clicked="dataNodeClicked"
    />

    <FormulaInputContext
      v-if="isFocused && !readOnly"
      ref="formulaInputContext"
      :node-selected="nodeSelected"
      :loading="loading"
      :mode="mode"
      @node-selected="handleNodeSelected"
      @node-unselected="unSelectNode()"
      @mode-changed="handleModeChange"
      @mousedown.native="onDataExplorerMouseDown"
    />

    <NodeHelpTooltip
      ref="nodeHelpTooltip"
      :node="hoveredFunctionNode"
      :nodes-hierarchy="nodesHierarchy"
    />
  </div>
</template>

<script>
import { Editor, EditorContent, generateHTML, Node } from '@tiptap/vue-2'
import { Placeholder } from '@tiptap/extension-placeholder'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { History } from '@tiptap/extension-history'
import { FunctionHighlightExtension } from '@baserow/modules/core/components/formula/FunctionHighlightExtension'
import { FunctionAutoCompleteExtension } from '@baserow/modules/core/components/formula/FunctionAutoCompleteExtension'
import { FunctionDeletionExtension } from '@baserow/modules/core/components/formula/FunctionDeletionExtension'
import { FunctionHelpTooltipExtension } from '@baserow/modules/core/components/formula/FunctionHelpTooltipExtension'
import {
  FormulaInsertionExtension,
  GetFormulaComponentNode,
} from '@baserow/modules/core/components/formula/FormulaInsertionExtension'
import { NodeSelectionExtension } from '@baserow/modules/core/components/formula/NodeSelectionExtension'
import { ContextManagementExtension } from '@baserow/modules/core/components/formula/ContextManagementExtension'
import _ from 'lodash'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import { mergeAttributes } from '@tiptap/core'
import FormulaInputContext from '@baserow/modules/core/components/formula/FormulaInputContext'
import NodeHelpTooltip from '@baserow/modules/core/components/nodeExplorer/NodeHelpTooltip'

export default {
  name: 'FormulaInputField',
  components: {
    FormulaInputContext,
    EditorContent,
    NodeHelpTooltip,
  },
  provide() {
    return {
      nodesHierarchy: this.nodesHierarchy,
    }
  },
  inject: {
    forInput: { from: 'forInput', default: null },
  },
  props: {
    value: {
      type: String,
      default: '',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    placeholder: {
      type: String,
      default: null,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    nodesHierarchy: {
      type: Array,
      required: false,
      default: () => [],
    },
    mode: {
      type: String,
      required: false,
      default: 'advanced',
      validator: (value) => {
        return ['advanced', 'simple', 'raw'].includes(value)
      },
    },
    contextPosition: {
      type: String,
      required: false,
      default: 'bottom',
      validator: (value) => {
        return ['bottom', 'left', 'right'].includes(value)
      },
    },
  },
  data() {
    return {
      editor: null,
      content: null,
      isFormulaInvalid: false,
      isFocused: false,
      hoveredFunctionNode: null,
    }
  },
  computed: {
    classes() {
      return {
        'form-input--disabled': this.disabled,
        'formula-input-field--small': this.small,
        'formula-input-field--focused':
          !this.disabled && !this.readOnly && this.isFocused,
        'formula-input-field--disabled': this.disabled,
        'form-input--error': this.isFormulaInvalid,
      }
    },
    placeHolderExt() {
      return Placeholder.configure({
        placeholder: this.placeholder,
      })
    },
    formulaComponents() {
      return Object.values(this.$registry.getAll('runtimeFormulaFunction'))
        .map((type) => type.formulaComponent)
        .filter((component) => component !== null)
    },
    wrapperNode() {
      return Node.create({
        name: 'wrapper',
        group: 'block',
        content: 'inline*',
        parseHTML() {
          return [{ tag: 'div' }]
        },
        renderHTML({ HTMLAttributes }) {
          return ['div', mergeAttributes(HTMLAttributes), 0]
        },
      })
    },
    functionNames() {
      const extract = (nodes) => {
        let names = []
        if (!nodes) {
          return names
        }
        for (const node of nodes) {
          if (node.type === 'function' && node.signature) {
            names.push(node.name)
          }
          const children = node.nodes
          if (children) {
            names = names.concat(extract(children))
          }
        }
        return names
      }
      return extract(this.nodesHierarchy)
    },
    operators() {
      const extract = (nodes) => {
        let operators = []
        if (!nodes) {
          return operators
        }
        for (const node of nodes) {
          if (
            node.type === 'operator' &&
            node.signature &&
            node.signature.operator
          ) {
            operators.push(node.signature.operator)
          }
          const children = node.nodes
          if (children) {
            operators = operators.concat(extract(children))
          }
        }
        return operators
      }
      return extract(this.nodesHierarchy)
    },
    extensions() {
      const DocumentNode = Document.extend()
      const TextNode = Text.extend({ inline: true })

      return [
        DocumentNode,
        this.wrapperNode,
        TextNode,
        GetFormulaComponentNode,
        this.placeHolderExt,
        History.configure({
          depth: 100,
        }),
        FunctionHighlightExtension.configure({
          functionNames: this.functionNames,
          operators: this.operators,
        }),
        FunctionAutoCompleteExtension.configure({
          functionNames: this.functionNames,
        }),
        FunctionDeletionExtension.configure({
          functionNames: this.functionNames,
        }),
        FormulaInsertionExtension.configure({
          vueComponent: this,
        }),
        NodeSelectionExtension.configure({
          vueComponent: this,
        }),
        ContextManagementExtension.configure({
          vueComponent: this,
          contextPosition: this.contextPosition,
          disabled: this.disabled,
          readOnly: this.readOnly,
        }),
        FunctionHelpTooltipExtension.configure({
          vueComponent: this,
        }),
        ...this.formulaComponents,
      ]
    },
    htmlContent() {
      try {
        return generateHTML(this.content, this.extensions)
      } catch (e) {
        console.error('Error while parsing formula content', this.value)
        console.error(e)
        return generateHTML(this.toContent(''), this.extensions)
      }
    },
    wrapperContent() {
      return this.editor.getJSON()
    },
    nodeSelected() {
      return this.editor?.commands.getSelectedNodePath() || null
    },
  },
  watch: {
    disabled(newValue) {
      this.editor.setOptions({ editable: !newValue && !this.readOnly })
    },
    readOnly(newValue) {
      this.editor.setOptions({ editable: !this.disabled && !newValue })
    },

    value(value) {
      if (!_.isEqual(value, this.toFormula(this.wrapperContent))) {
        const content = this.toContent(value)

        if (!this.isFormulaInvalid) {
          this.content = content
        }
      }
    },
    content: {
      handler() {
        if (this.editor && !_.isEqual(this.content, this.editor.getJSON())) {
          this.editor.commands.setContent(this.htmlContent, false, {
            preserveWhitespace: 'full',
            addToHistory: false,
          })
        }
      },
      deep: true,
    },
  },
  mounted() {
    this.content = this.toContent(this.value)
    this.editor = new Editor({
      content: this.htmlContent,
      editable: !this.disabled && !this.readOnly,
      onUpdate: this.onUpdate,
      extensions: this.extensions,
      parseOptions: {
        preserveWhitespace: 'full',
      },
      editorProps: {},
    })
  },
  beforeDestroy() {
    this.editor?.destroy()
  },
  methods: {
    resetField() {
      this.isFormulaInvalid = false
      this.$emit('input', '')
    },
    emitChange() {
      if (!this.isFormulaInvalid) {
        this.$emit('input', this.toFormula(this.wrapperContent))
      }
    },
    onUpdate() {
      this.emitChange()
    },
    handleNodeSelected({ path, node }) {
      switch (node.type) {
        case 'data':
          this.editor.commands.insertDataComponent(path)
          break
        case 'function':
          this.editor.commands.insertFunction(node)
          break
        case 'operator':
          this.editor.commands.insertOperator(node)
          break
        default:
          break
      }
    },
    onDataExplorerMouseDown() {
      this.editor?.commands.handleDataExplorerMouseDown()
    },
    toContent(formula) {
      if (!formula) {
        return {
          type: 'doc',
          content: [{ type: 'wrapper' }],
        }
      }

      if (this.readOnly) {
        return {
          type: 'doc',
          content: [
            {
              type: 'wrapper',
              content: [
                {
                  type: 'text',
                  text: formula,
                },
              ],
            },
          ],
        }
      }

      try {
        const tree = parseBaserowFormula(formula)
        const functionCollection = new RuntimeFunctionCollection(this.$registry)
        return new ToTipTapVisitor(functionCollection).visit(tree)
      } catch (error) {
        this.isFormulaInvalid = true
        return null
      }
    },
    toFormula(content) {
      const functionCollection = new RuntimeFunctionCollection(this.$registry)
      try {
        const formula = new FromTipTapVisitor(functionCollection).visit(content)

        return formula
      } catch (error) {
        this.isFormulaInvalid = true
        return null
      }
    },
    dataNodeClicked(node) {
      this.editor.commands.selectNode(node)
    },

    handleModeChange(newMode) {
      if (this.mode === 'advanced' && newMode === 'simple') {
        this.editor.commands.clearContent()
        this.$emit('input', '')
      }
      this.$emit('update:mode', newMode)
    },
    undo() {
      if (this.editor) {
        this.editor.commands.undo()
      }
    },
    redo() {
      if (this.editor) {
        this.editor.commands.redo()
      }
    },
  },
}
</script>
