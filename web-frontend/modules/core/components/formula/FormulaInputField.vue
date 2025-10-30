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
    <FormInput
      v-else
      v-model="advancedFormulaValue"
      type="text"
      :class="classes"
      role="textbox"
      :disabled="disabled"
      :placeholder="placeholder"
      @input="emitAdvancedChange"
    />

    <div v-if="showAdvancedCheckbox" class="margin-top-1">
      <label class="checkbox">
        <Checkbox
          :checked="isAdvancedMode"
          :disabled="disabled"
          @input="toggleMode()"
        >
          {{ $t('formulaInputField.advancedFormulaMode') }}
        </Checkbox>
      </label>
    </div>

    <DataExplorer
      v-if="isFocused && !isAdvancedMode"
      ref="dataExplorer"
      :nodes="nodes"
      :node-selected="nodeSelected"
      :loading="dataExplorerLoading"
      :application-context="applicationContext"
      :allow-node-selection="allowNodeSelection"
      @node-selected="dataExplorerItemSelected"
      @node-unselected="unSelectNode()"
      @mousedown.native="onDataExplorerMouseDown"
    />
  </div>
</template>

<script>
import { Editor, EditorContent, generateHTML, Node } from '@tiptap/vue-2'
import { Placeholder } from '@tiptap/extension-placeholder'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import _ from 'lodash'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import { mergeAttributes } from '@tiptap/core'
import DataExplorer from '@baserow/modules/core/components/dataExplorer/DataExplorer'
import { RuntimeGet } from '@baserow/modules/core/runtimeFormulaTypes'
import { isElement, onClickOutside } from '@baserow/modules/core/utils/dom'
import { isFormulaValid } from '@baserow/modules/core/formula'
import { FF_ADVANCED_FORMULA } from '@baserow/modules/core/plugins/featureFlags'

export default {
  name: 'FormulaInputField',
  components: {
    DataExplorer,
    EditorContent,
  },
  provide() {
    // Provide the application context to all formula components
    return {
      applicationContext: this.applicationContext,
      dataProviders: this.dataProviders,
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
      required: true,
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    enableAdvancedMode: {
      type: Boolean,
      required: false,
      default: false,
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
    },
  },
  data() {
    return {
      editor: null,
      content: null,
      isFormulaInvalid: false,
      dataNodeSelected: null,
      isFocused: false,
      ignoreNextBlur: false,
      advancedFormulaValue: this.value,
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
        'formula-input-field--focused': !this.disabled && this.isFocused,
        'formula-input-field--disabled': this.disabled,
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
    extensions() {
      const DocumentNode = Document.extend()
      const TextNode = Text.extend({ inline: true })

      return [
        DocumentNode,
        this.wrapperNode,
        TextNode,
        this.placeHolderExt,
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
    nodes() {
      return this.dataProviders
        .map((dataProvider) => dataProvider.getNodes(this.applicationContext))
        .filter((dataProviderNodes) => dataProviderNodes.nodes?.length > 0)
    },
    nodeSelected() {
      return this.dataNodeSelected?.attrs?.path || null
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
      this.editor.setOptions({ editable: !newValue })
    },
    async isFocused(value) {
      if (!value) {
        this.$refs.dataExplorer?.hide()
        this.unSelectNode()
      } else {
        // Don't show data explorer in Advanced mode
        if (this.isAdvancedMode) {
          return
        }

        // Wait for the data explorer to appear in the DOM.
        await this.$nextTick()

        this.unSelectNode()

        /**
         * The Context.vue calculates where to display the Context menu
         * relative to the input field that triggered it. When the Context
         * decides that the Context menu should be top-adjusted, it will set
         * its bottom coordinate to match the input field's top coordinate,
         * plus a "margin". This "margin" is the verticalOffset and is a
         * negative number; it is negative because the Context menu should not
         * appear below the input field.
         *
         * When the Context menu's bottom coordinate is less than zero, it
         * is hidden.
         *
         * By setting the verticalOffset to the negative value of the input
         * field's height, we ensure that as long as the input field is within
         * the viewport, the bottom coordinate of the Context menu is always
         * >= the bottom coordinate of the input field that triggered it.
         */
        const verticalOffset = -Math.abs(
          this.$el.getBoundingClientRect().height
        )

        this.$refs.dataExplorer.show(
          this.$refs.editor.$el,
          'bottom',
          'left',
          verticalOffset,
          -330
        )
      }
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
        if (!_.isEqual(this.content, this.editor.getJSON())) {
          this.editor?.commands.setContent(this.htmlContent, false, {
            preserveWhitespace: 'full',
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
      editable: !this.disabled,
      onUpdate: this.onUpdate,
      onFocus: this.onFocus,
      onBlur: this.onBlur,
      extensions: this.extensions,
      parseOptions: {
        preserveWhitespace: 'full',
      },
      editorProps: {
        handleClick: this.unSelectNode,
      },
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
      if (this.isFormulaInvalid) {
        return
      }

      const formulaValue = this.toFormula(this.wrapperContent)
      this.$emit('input', formulaValue)
    },
    toggleMode() {
      this.$emit('mode-changed', this.mode === 'simple' ? 'advanced' : 'simple')
    },
    onUpdate() {
      this.unSelectNode()
      this.emitChange()
    },
    onFocus(event) {
      // If the input is disabled, we don't want users to be
      // able to open the data explorer and select nodes.
      if (this.disabled) {
        return
      }
      this.isFocused = true

      this.$el.clickOutsideEventCancel = onClickOutside(
        this.$el,
        (target, event) => {
          if (
            this.$refs.dataExplorer &&
            // We ignore clicks inside data explorer
            !isElement(this.$refs.dataExplorer.$el, target)
          ) {
            this.isFocused = false
            this.editor.commands.blur()
            this.$el.clickOutsideEventCancel()
          }
        }
      )
    },
    onDataExplorerMouseDown() {
      // If we click in the data explorer we don't want to close it.
      this.ignoreNextBlur = true
    },
    onBlur() {
      if (this.ignoreNextBlur) {
        // Last click was in the data explorer context, we keep the focus.
        this.ignoreNextBlur = false
      } else {
        this.isFocused = false
      }
    },
    toContent(formula) {
      if (!formula) {
        return {
          type: 'doc',
          content: [{ type: 'wrapper' }],
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
        return new FromTipTapVisitor(functionCollection).visit(content)
      } catch (error) {
        this.isFormulaInvalid = true
        return null
      }
    },
    dataComponentClicked(node) {
      this.selectNode(node)
    },
    dataExplorerItemSelected({ path }) {
      const isInEditingMode = this.dataNodeSelected !== null
      if (isInEditingMode) {
        this.dataNodeSelected.attrs.path = path
        this.emitChange()
      } else {
        const getNode = new RuntimeGet().toNode([{ text: path }])
        this.editor.commands.insertContent(getNode)
      }
      this.editor.commands.focus()
    },
    selectNode(node) {
      if (node) {
        this.unSelectNode()
        this.dataNodeSelected = node
        this.dataNodeSelected.attrs.isSelected = true
      }
    },
    unSelectNode() {
      if (this.dataNodeSelected) {
        this.dataNodeSelected.attrs.isSelected = false
        this.dataNodeSelected = null
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
