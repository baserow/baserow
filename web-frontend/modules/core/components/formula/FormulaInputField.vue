<template>
  <div ref="formulaInputRoot">
    <div class="formula-input-field__editor" @click="handleEditorClick">
      <EditorContent
        :id="forInput"
        :key="key"
        ref="editor"
        class="form-input formula-input-field"
        role="textbox"
        :class="classes"
        :editor="editor"
        :style="{ '--formula-placeholder': `'${placeholder}'` }"
        @data-node-clicked="dataNodeClicked"
      />
    </div>

    <FormulaInputContext
      v-if="isFocused && !readOnly"
      ref="formulaInputContext"
      :node-selected="nodeSelected"
      :loading="loading"
      :mode="mode"
      :has-value="value.length > 0"
      :allow-node-selection="allowNodeSelection"
      :nodes-hierarchy="nodesHierarchy"
      :enabled-modes="enabledModes"
      @node-selected="handleNodeSelected"
      @node-unselected="unSelectNode"
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
import { Editor, EditorContent, Node } from '@tiptap/vue-2'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { History } from '@tiptap/extension-history'
import { HardBreak } from '@tiptap/extension-hard-break'
import { ArrowKeyNavigationExtension } from '@baserow/modules/core/components/formula/extensions/ArrowKeyNavigationExtension'
import { SmartDeletionExtension } from '@baserow/modules/core/components/formula/extensions/SmartDeletionExtension'
import { ZWSManagementExtension } from '@baserow/modules/core/components/formula/extensions/ZWSManagementExtension'
import { FunctionHelpTooltipExtension } from '@baserow/modules/core/components/formula/extensions/FunctionHelpTooltipExtension'
import {
  FormulaInsertionExtension,
  FunctionFormulaComponentNode,
  FunctionArgumentCommaNode,
  FunctionClosingParenNode,
  GroupOpeningParenNode,
  GroupClosingParenNode,
  OperatorFormulaComponentNode,
} from '@baserow/modules/core/components/formula/extensions/FormulaNodes'
import { NodeSelectionExtension } from '@baserow/modules/core/components/formula/extensions/NodeSelectionExtension'
import { ContextManagementExtension } from '@baserow/modules/core/components/formula/extensions/ContextManagementExtension'
import { FunctionDetectionExtension } from '@baserow/modules/core/components/formula/extensions/FunctionDetectionExtension'
import { GroupDetectionExtension } from '@baserow/modules/core/components/formula/extensions/GroupDetectionExtension'
import { OperatorDetectionExtension } from '@baserow/modules/core/components/formula/extensions/OperatorDetectionExtension'
import {
  createClipboardTextSerializer,
  createPasteHandler,
} from '@baserow/modules/core/components/formula/extensions/FormulaClipboardHandler'
import _ from 'lodash'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import { mergeAttributes } from '@tiptap/core'
import FormulaInputContext from '@baserow/modules/core/components/formula/FormulaInputContext'
import { isFormulaValid } from '@baserow/modules/core/formula'
import NodeHelpTooltip from '@baserow/modules/core/components/nodeExplorer/NodeHelpTooltip'
import { fixPropertyReactivityForProvide } from '@baserow/modules/core/utils/object'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

export default {
  name: 'FormulaInputField',
  components: {
    FormulaInputContext,
    EditorContent,
    NodeHelpTooltip,
  },

  provide() {
    return fixPropertyReactivityForProvide(
      {},
      {
        nodesHierarchy: () => this.nodesHierarchy,
      }
    )
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
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
    mode: {
      type: String,
      required: false,
      default: 'simple',
      validator: (value) => {
        return BASEROW_FORMULA_MODES.includes(value)
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
    /**
     * An array of Baserow formula modes which the parent formula input
     * component allows to be used. By default, we will allow all modes.
     */
    enabledModes: {
      type: Array,
      required: false,
      default: () => BASEROW_FORMULA_MODES,
    },
  },
  data() {
    return {
      editor: null,
      content: null,
      isFormulaInvalid: false,
      isFocused: false,
      hoveredFunctionNode: null,
      isHandlingModeChange: false,
      intersectionObserver: null,
      key: 0,
    }
  },
  computed: {
    isFormulaEmpty() {
      if (!this.editor) return true
      const formula = this.toFormula(this.wrapperContent)
      return !formula || formula.length === 0
    },
    classes() {
      return {
        'form-input--disabled': this.disabled,
        'formula-input-field--small': this.small,
        'formula-input-field--focused':
          !this.disabled && !this.readOnly && this.isFocused,
        'formula-input-field--disabled': this.disabled,
        'formula-input-field--error': this.isFormulaInvalid,
        'formula-input-field--formula-empty': this.isFormulaEmpty,
      }
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
    functionDefinitions() {
      const definitions = {}
      const extract = (nodes) => {
        if (!nodes) {
          return
        }
        for (const node of nodes) {
          if (node.type === 'function' && node.signature) {
            definitions[node.name.toLowerCase()] = node
          }
          const children = node.nodes
          if (children) {
            extract(children)
          }
        }
      }

      extract(this.nodesHierarchy)
      return definitions
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

      const extensions = [
        DocumentNode,
        this.wrapperNode,
        TextNode,
        ArrowKeyNavigationExtension,
        SmartDeletionExtension,
        ZWSManagementExtension,
        History.configure({
          depth: 100,
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
          functionDefinitions: this.functionDefinitions,
        }),
        ...this.formulaComponents,
      ]

      if (this.mode === 'advanced') {
        extensions.push(FunctionFormulaComponentNode)
        extensions.push(FunctionArgumentCommaNode)
        extensions.push(FunctionClosingParenNode)
        extensions.push(GroupOpeningParenNode)
        extensions.push(GroupClosingParenNode)
        extensions.push(OperatorFormulaComponentNode)
        extensions.push(
          HardBreak.extend({
            addKeyboardShortcuts() {
              return {
                Enter: () => this.editor.commands.setHardBreak(),
              }
            },
          })
        )
        extensions.push(
          FunctionDetectionExtension.configure({
            functionNames: this.functionNames,
            functionDefinitions: this.functionDefinitions,
          }),
          GroupDetectionExtension.configure({
            functionNames: this.functionNames,
          }),
          OperatorDetectionExtension.configure({
            operators: this.operators,
            vueComponent: this,
          })
        )
      }

      return extensions
    },
    wrapperContent() {
      return this.editor.getJSON()
    },
    nodeSelected() {
      return this.editor?.commands.getSelectedNodePath() || null
    },
  },
  watch: {
    nodesHierarchy() {
      // fixes reactivity issue with components in tiptap by forcing the input to
      // render.
      this.key += 1
    },
    disabled(newValue) {
      this.editor.setOptions({ editable: !newValue && !this.readOnly })
    },
    readOnly(newValue) {
      this.editor.setOptions({ editable: !this.disabled && !newValue })
    },

    mode(newMode, oldMode) {
      // Skip automatic recreation if we're handling it manually in handleModeChange
      if (this.isHandlingModeChange) {
        return
      }
      this.recreateEditor()
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
          this.editor.commands.setContent(this.content, false, {
            preserveWhitespace: 'full',
            addToHistory: false,
          })
        }
      },
      deep: true,
    },
  },
  mounted() {
    this.createEditor()
    this.setupIntersectionObserver()
  },
  beforeDestroy() {
    this.editor?.destroy()
    this.cleanupIntersectionObserver()
  },
  methods: {
    setupIntersectionObserver() {
      this.intersectionObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting && this.isFocused) {
              this.isFocused = false
              if (this.editor) {
                this.editor.commands.blur()
              }
            }
          })
        },
        {
          root: null,
          threshold: 0,
        }
      )

      if (this.$refs.formulaInputRoot) {
        this.intersectionObserver.observe(this.$refs.formulaInputRoot)
      }
    },
    cleanupIntersectionObserver() {
      if (this.intersectionObserver) {
        this.intersectionObserver.disconnect()
        this.intersectionObserver = null
      }
    },
    createEditor(formula = null) {
      // Use provided formula or fall back to the prop value
      this.content = this.toContent(formula || this.value)
      this.editor = new Editor({
        content: this.content,
        editable: !this.disabled && !this.readOnly,
        onUpdate: this.onUpdate,
        extensions: this.extensions,
        parseOptions: {
          preserveWhitespace: 'full',
        },
        editorProps: {
          clipboardTextSerializer: createClipboardTextSerializer(
            this.toFormula.bind(this)
          ),
          handlePaste: createPasteHandler({
            toContent: this.toContent.bind(this),
            getMode: () => this.mode,
          }),
        },
      })
    },
    recreateEditor(formula = null) {
      const currentFormula =
        formula ||
        (this.editor ? this.toFormula(this.wrapperContent) : this.value)

      this.editor?.destroy()
      this.createEditor(currentFormula)
    },
    emitChange() {
      const functions = new RuntimeFunctionCollection(this.$registry)
      const formula = this.toFormula(this.wrapperContent)
      this.isFormulaInvalid = !isFormulaValid(formula, functions)

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
        case 'array':
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
          content: [
            {
              type: 'wrapper',
              content: [{ type: 'text', text: '\u200B' }],
            },
          ],
        }
      }

      try {
        const tree = parseBaserowFormula(formula)
        const functionCollection = new RuntimeFunctionCollection(this.$registry)
        const result = new ToTipTapVisitor(functionCollection, this.mode).visit(
          tree
        )

        // Ensure wrapper always starts with a ZWS
        if (result && result.content && result.content[0]) {
          const wrapper = result.content[0]
          if (wrapper.type === 'wrapper') {
            if (!wrapper.content || wrapper.content.length === 0) {
              wrapper.content = [{ type: 'text', text: '\u200B' }]
            } else {
              const firstNode = wrapper.content[0]
              // Add ZWS at the beginning if it's not already there
              if (
                !firstNode ||
                firstNode.type !== 'text' ||
                firstNode.text !== '\u200B'
              ) {
                wrapper.content.unshift({ type: 'text', text: '\u200B' })
              }
            }
          }
        }

        return result
      } catch (error) {
        return null
      }
    },
    toFormula(content, mode = null) {
      const functionCollection = new RuntimeFunctionCollection(this.$registry)
      try {
        const formula = new FromTipTapVisitor(
          functionCollection,
          mode || this.mode
        ).visit(content)

        return formula
      } catch (error) {
        return null
      }
    },
    dataNodeClicked(node) {
      this.editor.commands.selectNode(node)
    },
    handleEditorClick() {
      if (this.editor && !this.disabled && !this.readOnly) {
        this.editor.commands.showContext()
      }
    },
    handleModeChange(newMode) {
      // If switching from advanced to simple, clear the content
      if (this.mode === 'advanced' && newMode === 'simple') {
        this.isHandlingModeChange = true
        this.editor.commands.clearContent()
        this.$emit('update:mode', newMode)
        this.$emit('input', '')
        this.isFormulaInvalid = false
        this.isHandlingModeChange = false
      } else {
        // Otherwise (simple to advanced), keep the current formula
        // Get the formula BEFORE changing the mode, using the CURRENT mode
        const currentFormula = this.toFormula(this.wrapperContent, this.mode)

        // Set flag to prevent automatic recreation from watcher
        this.isHandlingModeChange = true

        // Update the mode
        this.$emit('update:mode', newMode)

        // Wait for Vue to update the mode prop
        this.$nextTick(() => {
          // Recreate the editor with the new mode and preserved formula
          this.recreateEditor(currentFormula)

          // Emit the formula value
          if (currentFormula) {
            this.$emit('input', currentFormula)
          }

          // Reset the flag
          this.isHandlingModeChange = false
        })
      }
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
    unSelectNode() {
      this.editor?.commands.unselectNode()
    },
  },
}
</script>
