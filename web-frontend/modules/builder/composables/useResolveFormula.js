// composables/useResolveFormula.js
import { computed, unref } from 'vue'
import { useNuxtApp } from '#app'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula as coreResolveFormula } from '@baserow/modules/core/formula'

/**
 * Composable replacement for the resolveFormula mixin.
 *
 * @param {Object|Ref<Object>} applicationContext
 *   Usually the result of useApplicationContext().applicationContext
 *
 * Usage:
 *   const { applicationContext } = useApplicationContext(props)
 *   const { runtimeFormulaContext, formulaFunctions, resolveFormula } =
 *     useResolveFormula(applicationContext)
 */
export function useResolveFormula({ applicationContext }) {
  const { $registry } = useNuxtApp()

  const runtimeFormulaContext = computed(() => {
    /**
     * This proxy allows the RuntimeFormulaContext class to act like a regular object.
     */
    const ctx = new RuntimeFormulaContext(
      $registry.getAll('builderDataProvider'),
      unref(applicationContext)
    )

    return new Proxy(ctx, {
      get(target, prop) {
        return target.get(prop)
      },
    })
  })

  const formulaFunctions = {
    get(name) {
      return $registry.get('runtimeFormulaFunction', name)
    },
  }

  function resolveFormula(formula, formulaContext = null, defaultIfError = '') {
    try {
      return coreResolveFormula(
        formula,
        formulaFunctions,
        formulaContext || unref(runtimeFormulaContext)
      )
    } catch (e) {
      return defaultIfError
    }
  }

  return {
    //runtimeFormulaContext,
    //formulaFunctions,
    resolveFormula,
  }
}
