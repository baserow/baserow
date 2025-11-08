import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula } from '@baserow/modules/core/formula'
import { resolveColor } from '@baserow/modules/core/utils/colors'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

export default {
  inject: ['workspace', 'builder', 'currentPage', 'elementPage', 'mode'],
  mixins: [applicationContextMixin],
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
    elementIsInError() {
      return this.elementType.isInError({
        workspace: this.workspace,
        page: this.elementPage,
        element: this.element,
        builder: this.builder,
      })
    },
    runtimeFormulaContext() {
      /**
       * This proxy allow the RuntimeFormulaContextClass to act like a regular object.
       */
      return new Proxy(
        new RuntimeFormulaContext(
          this.$registry.getAll('builderDataProvider'),
          this.applicationContext
        ),
        {
          get(target, prop) {
            return target.get(prop)
          },
        }
      )
    },
    formulaFunctions() {
      return {
        get: (name) => {
          return this.$registry.get('runtimeFormulaFunction', name)
        },
      }
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
    resolveFormula(formula, formulaContext = null, defaultIfError = '') {
      try {
        return resolveFormula(
          formula,
          this.formulaFunctions,
          formulaContext || this.runtimeFormulaContext
        )
      } catch (e) {
        return defaultIfError
      }
    },
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
