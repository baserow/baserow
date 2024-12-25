<template>
  <Alert v-if="isFormulaInvalid" type="error">
    <p>
      {{ $t('formulaInputField.errorInvalidFormula') }}
    </p>
    <template #actions>
      <Button type="danger" size="small" @click.prevent="reset">
        {{ $t('action.reset') }}
      </Button>
    </template>
  </Alert>
  <div v-else>
    <EditorContent
      ref="editor"
      class="form-input formula-input-field"
      role="textbox"
      :class="classes"
      :editor="editor"
      @data-component-clicked="dataComponentClicked"
    />
    <DataExplorer
      v-if="isFocused"
      ref="dataExplorer"
      :nodes="nodes"
      :node-selected="nodeSelected"
      :loading="dataExplorerLoading"
      :application-context="applicationContext"
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
  },
  data() {
    return {
      editor: null,
      content: null,
      isFormulaInvalid: false,
      dataNodeSelected: null,
      isFocused: false,
      ignoreNextBlur: false,
    }
  },
  computed: {
    classes() {
      return {
        'form-input--disabled': this.disabled,
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
      return generateHTML(this.content, this.extensions)
    },
    wrapperContent() {
      return this.editor.getJSON()
    },
    nodes() {
      const nodes = this.dataProviders
        .map((dataProvider) => dataProvider.getNodes(this.applicationContext))
        .filter((dataProviderNodes) => dataProviderNodes.nodes?.length > 0)
      return nodes
    },
    nodeSelected() {
      return this.dataNodeSelected?.attrs?.path || null
    },
  },
  watch: {
    disabled(newValue) {
      this.editor.setOptions({ editable: !newValue })
    },
    async isFocused(value) {
      if (!value) {
        this.$refs.dataExplorer.hide()
        this.unSelectNode()
      } else {
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
  },
  mounted() {
    this.content = this.toContent(this.value)
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
    reset() {
      this.isFormulaInvalid = false
      this.$emit('input', '')
    },
    emitChange() {
      if (!this.isFormulaInvalid) {
        this.$emit('input', this.toFormula(this.wrapperContent))
      }
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
  },
}
</script>
