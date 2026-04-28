<template>
  <div ref="formulaInputRoot">
    <div
      ref="formulaEditorSurface"
      class="formula-input-field__editor"
      @click="handleEditorClick"
    >
      <EditorContent
        :id="forInput"
        ref="editor"
        class="form-input formula-input-field"
        role="textbox"
        :class="classes"
        :editor="editor"
        :style="{ '--formula-placeholder': `'${placeholder}'` }"
      />
    </div>

    <FormulaInputErrorContext
      :visible="showErrorContext"
      :formula-error-context="formulaErrorContext"
      :target="$refs.formulaEditorSurface"
      @mousedown="onContextMouseDown"
    />

    <FormulaInputExplorerContext
      v-if="isFocused && !readOnly"
      ref="formulaInputExplorerContext"
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
      @mousedown="onContextMouseDown"
    />

    <NodeHelpTooltip
      ref="nodeHelpTooltip"
      :node="hoveredFunctionNode"
      :nodes-hierarchy="nodesHierarchy"
    />
  </div>
</template>

<script>
import { Editor, EditorContent, Node } from '@tiptap/vue-3'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { History } from '@tiptap/extension-history'
import { HardBreak } from '@tiptap/extension-hard-break'
import { ArrowKeyNavigationExtension } from '@baserow/modules/core/components/formula/extensions/ArrowKeyNavigationExtension'
import { SmartDeletionExtension } from '@baserow/modules/core/components/formula/extensions/SmartDeletionExtension'
import { ZWSManagementExtension } from '@baserow/modules/core/components/formula/extensions/ZWSManagementExtension'
import { FunctionHelpTooltipExtension } from '@baserow/modules/core/components/formula/extensions/FunctionHelpTooltipExtension'
import { ParenMatchHighlightExtension } from '@baserow/modules/core/components/formula/extensions/ParenMatchHighlightExtension'
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
import { InputDetectionExtension } from '@baserow/modules/core/components/formula/extensions/InputDetectionExtension'
import { FunctionDowngradeExtension } from '@baserow/modules/core/components/formula/extensions/FunctionDowngradeExtension'
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
import FormulaInputErrorContext from '~/modules/core/components/formula/FormulaInputErrorContext'
import FormulaInputExplorerContext from '@baserow/modules/core/components/formula/FormulaInputExplorerContext'
import { isFormulaValid } from '@baserow/modules/core/formula'
import NodeHelpTooltip from '@baserow/modules/core/components/nodeExplorer/NodeHelpTooltip'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

/**
 * The ANTLR lexer's INTEGER_LITERAL / NUMERIC_LITERAL rules include an
 * optional leading '-', so the lexer greedily tokenizes e.g. ")-200" as
 * CLOSE_PAREN INTEGER_LITERAL(-200) instead of CLOSE_PAREN MINUS
 * INTEGER_LITERAL(200). This inserts a space before '-' when it acts as a
 * binary operator (preceded by a character that ends an expression) so the
 * lexer produces a separate MINUS token.
 */
export function disambiguateMinusOperator(formula) {
  let result = ''
  let inString = false
  let quoteChar = null

  for (let i = 0; i < formula.length; i++) {
    const ch = formula[i]

    if (inString) {
      result += ch
      if (ch === '\\' && i + 1 < formula.length) {
        result += formula[++i]
      } else if (ch === quoteChar) {
        inString = false
      }
      continue
    }

    if (ch === "'" || ch === '"') {
      inString = true
      quoteChar = ch
      result += ch
      continue
    }

    if (
      ch === '-' &&
      i + 1 < formula.length &&
      /\d/.test(formula[i + 1]) &&
      i > 0 &&
      /[)\d\w]/.test(formula[i - 1])
    ) {
      result += ' - '
      continue
    }

    result += ch
  }

  return result
}

export default {
  name: 'FormulaInputField',
  components: {
    FormulaInputErrorContext,
    FormulaInputExplorerContext,
    EditorContent,
    NodeHelpTooltip,
  },

  provide() {
    return { nodesHierarchy: computed(() => this.nodesHierarchy) }
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
    validationContext: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  emits: ['input', 'update:mode'],
  data() {
    return {
      editor: null,
      content: null,
      isFormulaInvalid: false,
      formulaErrorContext: { scope: null, title: '', message: '' },
      errorExpanded: false,
      isFocused: false,
      hoveredFunctionNode: null,
      isHandlingModeChange: false,
      intersectionObserver: null,
      isEditorInitialized: false,
    }
  },
  computed: {
    showErrorContext() {
      return this.isFocused && !this.readOnly && this.isFormulaInvalid
    },
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
    formulaRegistry() {
      const names = []
      const definitions = {}
      const operators = []

      const extract = (nodes) => {
        if (!nodes) return
        for (const node of nodes) {
          if (node.type === 'function' && node.signature) {
            names.push(node.name)
            definitions[node.name.toLowerCase()] = node
          }
          if (node.type === 'operator' && node.signature?.operator) {
            operators.push(node.signature.operator)
          }
          if (node.nodes) extract(node.nodes)
        }
      }

      extract(this.nodesHierarchy)
      return { names, definitions, operators }
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
        FormulaInsertionExtension,
        NodeSelectionExtension,
        ContextManagementExtension.configure({
          getState: () => ({
            isFocused: this.isFocused,
            disabled: this.disabled,
            readOnly: this.readOnly,
          }),
          setFocused: (val) => {
            this.isFocused = val
          },
          getRootEl: () => this.$el,
          getContextEl: () =>
            this.$refs.formulaInputExplorerContext?.getTeleportedElement(),
          showExplorerContextMenu: () => {
            this.$nextTick(() => {
              if (!this.isFocused) return
              this.positionAndShowExplorerContext()
            })
          },
          hideContextMenu: () => {
            this.$refs.formulaInputExplorerContext?.hide()
          },
        }),
        FunctionHelpTooltipExtension.configure({
          functionDefinitions: this.formulaRegistry.definitions,
          onShowTooltip: (el, node) => {
            this.hoveredFunctionNode = node
            this.$refs.nodeHelpTooltip?.show(el, 'bottom', 'right', 6, 10)
          },
          onHideTooltip: () => {
            this.$refs.nodeHelpTooltip?.hide()
            this.hoveredFunctionNode = null
          },
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
          InputDetectionExtension.configure({
            functionNames: this.formulaRegistry.names,
            functionDefinitions: this.formulaRegistry.definitions,
            operators: this.formulaRegistry.operators,
          })
        )
        extensions.push(FunctionDowngradeExtension)
        extensions.push(ParenMatchHighlightExtension)
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
    disabled(newValue) {
      this.editor.setOptions({ editable: !newValue && !this.readOnly })
    },
    readOnly(newValue) {
      this.editor.setOptions({ editable: !this.disabled && !newValue })
    },

    mode(newMode, oldMode) {
      // In Vue 3, watchers can fire during the initial render cycle before
      // mounted() completes. Skip if editor hasn't been initialized yet.
      if (!this.isEditorInitialized) {
        return
      }
      // Skip automatic recreation if we're handling it manually in handleModeChange
      if (this.isHandlingModeChange) {
        return
      }
      this.recreateEditor()
    },

    value(value) {
      // Use editor.getJSON() directly instead of this.wrapperContent to avoid stale cached data
      const editorContent = this.editor?.getJSON()
      const currentFormula = this.toFormula(editorContent)
      if (!_.isEqual(value, currentFormula)) {
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
  beforeUnmount() {
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
      this.isEditorInitialized = true

      this.editor.on('data-node-clicked', this.dataNodeClicked)
    },
    recreateEditor(formula = null) {
      const currentFormula =
        formula ||
        (this.editor ? this.toFormula(this.wrapperContent) : this.value)

      this.editor?.destroy()
      this.createEditor(currentFormula)
    },
    emitChange() {
      this.formulaErrorContext = { scope: null, title: '', message: '' }
      this.errorExpanded = false

      const functions = new RuntimeFunctionCollection(this.$registry)
      // this.wrapperContent can be stale content, so get the data
      // directly from the editor.
      const editorContent = this.editor.getJSON()
      const formula = this.toFormula(editorContent)

      // Validate the syntax, and assuming it's valid, then validate the arguments.
      const validationResult = isFormulaValid(
        formula,
        functions,
        false,
        this.validationContext,
        this.$t('formulaInputField.invalidSyntax')
      )
      this.isFormulaInvalid = !validationResult.valid
      if (this.isFormulaInvalid) {
        this.formulaErrorContext = {
          scope: validationResult.scope,
          title: this.$t('formulaInputField.invalidFormulaTitle'),
          message: validationResult.errors[0],
        }
        this.$nextTick(() => {
          this.editor.commands.repositionContext()
        })
      } else {
        this.$emit('input', formula)
      }
    },
    onUpdate() {
      this.emitChange()
    },
    handleNodeSelected(data) {
      const { path, node } = data
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
    onContextMouseDown() {
      this.editor?.commands.handleContextMouseDown()
    },
    positionAndShowExplorerContext() {
      let config
      switch (this.contextPosition) {
        case 'left':
          config = {
            vertical: 'bottom',
            horizontal: 'left',
            needsDynamicOffset: true,
          }
          break
        case 'right':
          config = {
            vertical: 'bottom',
            horizontal: 'left',
            needsDynamicOffset: true,
          }
          break
        case 'bottom':
        default:
          config = {
            vertical: 'bottom',
            horizontal: 'left',
            verticalOffset: 10,
            horizontalOffset: 0,
          }
          break
      }

      const { vertical, horizontal } = config
      let { verticalOffset = 0, horizontalOffset = 0 } = config

      if (config.needsDynamicOffset) {
        const inputRect = this.$el?.getBoundingClientRect()
        const contextRect = this.$refs.formulaInputExplorerContext
          ?.getTeleportedElement()
          ?.getBoundingClientRect()

        switch (this.contextPosition) {
          case 'left':
            verticalOffset = -inputRect?.height || 0
            horizontalOffset = -(contextRect?.width || 0) - 10
            break
          case 'right':
            verticalOffset = -inputRect?.height || 0
            horizontalOffset = (inputRect?.width || 0) + 10
            break
        }
      }

      this.$refs.formulaInputExplorerContext?.show(
        this.$refs.editor.$el,
        vertical,
        horizontal,
        verticalOffset,
        horizontalOffset
      )
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
        const tree = parseBaserowFormula(
          disambiguateMinusOperator(formula),
          false
        )
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
        this.formulaErrorContext = { scope: null, title: '', message: '' }
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
