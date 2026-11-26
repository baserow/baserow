import { resolveColor } from '@baserow/modules/core/utils/colors'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'
import resolveFormulaMixin from '@baserow/modules/builder/mixins/resolveFormula'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

export default {
  inject: ['workspace', 'builder', 'currentPage', 'elementPage', 'mode'],
  mixins: [applicationContextMixin, resolveFormulaMixin],
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    workflowActionsInProgress() {
      const workflowActions = this.$store.getters[
        'builderWorkflowAction/getElementWorkflowActions'
      ](this.elementPage, this.element.id)
      const dispatchedById = this.elementType.uniqueElementId({
        element: this.element,
        applicationContext: this.applicationContext,
      })
      return workflowActions.some((workflowAction) =>
        this.$store.getters['builderWorkflowAction/getDispatching'](
          workflowAction,
          dispatchedById
        )
      )
    },
    elementType() {
      return this.$registry.get('element', this.element.type)
    },
    isEditMode() {
      return this.mode === 'editing'
    },
    /**
     * Restrict author code according to the hostname serving this page.
     */
    isAuthorCodeRestricted() {
      return this.$isAuthorCodeRestricted()
    },
    /**
     * The editor's hint for an element that holds author code. Preview only
     * shows such an element in full when it doesn't restrict that code.
     */
    authorCodeEditorHint() {
      return this.$previewRestrictsAuthorCode()
        ? this.$t('iframeElementForm.editorEmbedHintPublished')
        : this.$t('iframeElementForm.editorEmbedHint')
    },
    elementIsInError() {
      return this.elementType.isInError(this.element, this.applicationContext)
    },

    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
    colorVariables() {
      return ThemeConfigBlockType.getAllColorVariables(
        this.themeConfigBlocks,
        this.builder.theme
      )
    },
  },
  methods: {
    async fireEvent(event) {
      if (this.mode !== 'editing') {
        if (this.workflowActionsInProgress) {
          return false
        }

        const workflowActions = this.$store.getters[
          'builderWorkflowAction/getElementWorkflowActions'
        ](this.elementPage, this.element.id).filter(
          ({ event: eventName }) => eventName === event.name
        )

        await event.fire({
          workflowActions,
          resolveFormula: this.resolveFormula,
          applicationContext: this.applicationContext,
        })
      }
    },
    getStyleOverride(key, colorVariables = null) {
      return ThemeConfigBlockType.getAllStyles(
        this.themeConfigBlocks,
        this.element.styles?.[key] || {},
        colorVariables || this.colorVariables,
        this.builder.theme
      )
    },
    resolveColor,
  },
}
