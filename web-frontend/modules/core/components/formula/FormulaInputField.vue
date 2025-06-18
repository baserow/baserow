<template>
  <Alert v-if="isFormulaInvalid && mode == 'simple'" type="error">
    <p>
      {{ $t('formulaInputField.errorInvalidFormula') }}
    </p>
    <template #actions>
      <Button type="danger" size="small" @click.prevent="resetField">
        {{ $t('action.reset') }}
      </Button>
    </template>
  </Alert>
  <div v-else>
    <EditorContent
      v-if="!isAdvancedMode"
      :id="forInput"
      ref="editor"
      class="form-input formula-input-field"
      role="textbox"
      :class="classes"
      :editor="editor"
      @data-component-clicked="dataComponentClicked"
    />

    <FormulaInputContext
      v-if="isFocused && !readOnly"
      ref="formulaInputContext"
      :data-providers="dataProviders"
      :application-context="applicationContext"
      :node-selected="nodeSelected"
      :data-explorer-loading="dataExplorerLoading"
      :advanced="advanced"
      @node-selected="dataExplorerItemSelected"
      @node-unselected="unSelectNode()"
      @function-selected="onFunctionSelected"
      @operator-selected="onOperatorSelected"
      @toggle-advanced-mode="onAdvancedModeToggled"
      @mousedown.native="onDataExplorerMouseDown"
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
import { FormulaValidationExtension } from '@baserow/modules/core/components/formula/FormulaValidationExtension'
import { FormulaInsertionExtension } from '@baserow/modules/core/components/formula/FormulaInsertionExtension'
import { NodeSelectionExtension } from '@baserow/modules/core/components/formula/NodeSelectionExtension'
import { ContextManagementExtension } from '@baserow/modules/core/components/formula/ContextManagementExtension'
import _ from 'lodash'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import { mergeAttributes } from '@tiptap/core'
import FormulaInputContext from '@baserow/modules/core/components/formula/FormulaInputContext'

export default {
  name: 'FormulaInputField',
  components: {
    FormulaInputContext,
    EditorContent,
  },
  provide() {
    return {
      applicationContext: this.applicationContext,
      dataProviders: this.dataProviders,
      contextTabs: this.contextTabs,
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
    dataProviders: {
      type: Array,
      required: false,
      default: () => [],
    },
    dataExplorerLoading: {
      type: Boolean,
      required: false,
      default: false,
    },
    applicationContext: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    contextTabs: {
      type: Array,
      required: false,
      default: () => [],
    },
    advanced: {
      type: Boolean,
      required: false,
      default: false,
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
    }
  },
  computed: {
    isAdvancedMode() {
      return this.mode === 'advanced'
    },
    classes() {
      return {
        'form-input--disabled': this.disabled,
        'form-input--error': this.isFormulaInvalid,
        'formula-input-field--small': this.small,
        'formula-input-field--focused':
          !this.disabled && !this.readOnly && this.isFocused,
        'formula-input-field--disabled': this.disabled,
      }
    },
    functionSignatures() {
      const signatures = {}

      this.contextTabs.forEach((tab) => {
        if (tab.categories) {
          tab.categories.forEach((category) => {
            if (category.items) {
              category.items.forEach((item) => {
                if (item.signature) {
                  const {
                    parameters = [],
                    minArgs,
                    maxArgs,
                    variadic,
                  } = item.signature
                  signatures[item.name] = {
                    parameters,
                    minArgs:
                      minArgs || parameters.filter((p) => p.required).length,
                    maxArgs:
                      maxArgs || (variadic ? Infinity : parameters.length),
                    hasUnlimitedArgs: variadic || maxArgs === null,
                    returnType: item.signature.returnType || 'any',
                  }
                }
              })
            }
          })
        }
      })

      return signatures
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
      const functionsTab = this.contextTabs.find(
        (tab) => tab.name === 'Functions'
      )
      if (!functionsTab || !functionsTab.categories) return []

      const functionNames = []

      functionsTab.categories.forEach((category) => {
        if (category.items) {
          category.items.forEach((item) => {
            functionNames.push(item.name)
          })
        }
      })

      return functionNames
    },
    highlightingOperatorNames() {
      const operatorsTab = this.contextTabs.find(
        (tab) => tab.name === 'Operators'
      )
      if (!operatorsTab || !operatorsTab.categories) return []

      const operators = []

      operatorsTab.categories.forEach((category) => {
        if (category.items) {
          category.items.forEach((item) => {
            if (item.operator) {
              operators.push({
                ...item,
                value: item.name,
              })
            }
          })
        }
      })

      return operators
    },
    extensions() {
      const DocumentNode = Document.extend()
      const TextNode = Text.extend({ inline: true })

      return [
        DocumentNode,
        this.wrapperNode,
        TextNode,
        this.placeHolderExt,
        History.configure({
          depth: 100,
        }),
        FunctionHighlightExtension.configure({
          functionNames: this.functionNames,
          operators: this.highlightingOperatorNames,
        }),
        FunctionAutoCompleteExtension.configure({
          functionNames: this.functionNames,
        }),
        FunctionDeletionExtension.configure({
          functionNames: this.functionNames,
        }),
        FormulaValidationExtension.configure({
          functionSignatures: this.functionSignatures,
          dataProviders: this.dataProviders,
          applicationContext: this.applicationContext,
          vueComponent: this,
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
        ...this.formulaComponents,
      ]
    },
    htmlContent() {
      if (this.isAdvancedMode) {
        return ''
      }

      try {
        if (!this.content) {
          return generateHTML(this.toContent(''), this.extensions)
        }
        return generateHTML(this.content, this.extensions)
      } catch (e) {
        console.error('Error while parsing formula content', this.value)
        console.error(e)
        return generateHTML(this.toContent(''), this.extensions)
      }
    },
    wrapperContent() {
      if (this.isAdvancedMode || !this.editor) {
        return null
      }
      return this.editor.getJSON()
    },
    nodeSelected() {
      return this.editor?.commands.getSelectedNodePath() || null
    },
    showAdvancedCheckbox() {
      return (
        this.enableAdvancedMode &&
        this.$featureFlagIsEnabled(FF_ADVANCED_FORMULA)
      )
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
      // In advanced mode, just update the value directly
      if (this.isAdvancedMode) {
        this.advancedFormulaValue = value
        return
      }

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

    isAdvancedMode(newValue) {
      if (newValue) {
        // When switching to advanced mode, preserve current value
        this.advancedFormulaValue = this.value
        this.isFormulaInvalid = false
      } else {
        // When switching to simple mode, clear the value to avoid formula parsing errors
        this.advancedFormulaValue = ''
        this.$emit('input', this.advancedFormulaValue)
      }
    },
  },
  mounted() {
    if (!this.isAdvancedMode) {
      this.content = this.toContent(this.value)
    }

    this.editor = new Editor({
      content: this.htmlContent,
      editable: !this.disabled && !this.readOnly,
      extensions: this.extensions,
      parseOptions: {
        preserveWhitespace: 'full',
      },
      editorProps: {},
    })

    this.$on('validation-changed', this.onValidationChanged)
  },
  beforeDestroy() {
    this.$off('validation-changed', this.onValidationChanged)
    this.editor?.destroy()
  },
  methods: {
    resetField() {
      this.isFormulaInvalid = false
      this.$emit('input', '')
    },
    onValidationChanged({ isValid, errors }) {
      this.isFormulaInvalid = !isValid
      if (isValid) {
        const formula = this.toFormula(this.wrapperContent)
        this.$emit('input', formula)
      }

      const formulaValue = this.toFormula(this.wrapperContent)
      this.$emit('input', formulaValue)
    },
    toggleMode() {
      this.$emit('mode-changed', this.mode === 'simple' ? 'advanced' : 'simple')
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
    },
    toFormula(content) {
      const functionCollection = new RuntimeFunctionCollection(this.$registry)
      try {
        const formula = new FromTipTapVisitor(functionCollection).visit(content)

        return formula
      } catch (error) {
        return null
      }
    },
    dataComponentClicked(node) {
      this.editor.commands.selectNode(node)
    },
    dataExplorerItemSelected({ path }) {
      this.editor.commands.insertDataComponent(path)
    },
    onFunctionSelected(func) {
      this.editor.commands.insertFunction(func)
    },
    onOperatorSelected(operator) {
      this.editor.commands.insertOperator(operator)
    },

    onAdvancedModeToggled() {
      if (this.advanced) {
        this.editor.commands.clearContent()
        this.$emit('input', '')
      }

      this.$emit('update:advanced', !this.advanced)
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
    emitAdvancedChange() {
      const functions = new RuntimeFunctionCollection(this.$registry)
      if (isFormulaValid(this.advancedFormulaValue, functions)) {
        this.isFormulaInvalid = false
        this.$emit('input', this.advancedFormulaValue)
      } else {
        this.isFormulaInvalid = true
      }
    },
  },
}
</script>
