import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula } from '@baserow/modules/core/formula'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'

export default {
  mixins: [applicationContextMixin],
  computed: {
    runtimeFormulaContext() {
      return this.getRuntimeFormulaContext()
    },
    formulaFunctions() {
      return {
        get: (name) => {
          return this.$registry.get('runtimeFormulaFunction', name)
        },
      }
    },
  },
  methods: {
    /** Wrap an application context for runtime formula evaluation. */
    getRuntimeFormulaContext(applicationContext = this.applicationContext) {
      return new Proxy(
        new RuntimeFormulaContext(
          this.$registry.getAll('builderDataProvider'),
          applicationContext
        ),
        {
          get(target, prop) {
            return target.get(prop)
          },
        }
      )
    },
    /**
     * Resolve with a custom runtime context or a callback transforming the current
     * application context. Return a new context from the callback to keep other
     * formulas unaffected.
     */
    resolveFormula(formula, formulaContext = null, defaultIfError = '') {
      try {
        return resolveFormula(
          formula,
          this.formulaFunctions,
          typeof formulaContext === 'function'
            ? this.getRuntimeFormulaContext(
                formulaContext(this.applicationContext)
              )
            : formulaContext || this.runtimeFormulaContext
        )
      } catch (e) {
        return defaultIfError
      }
    },
  },
}
