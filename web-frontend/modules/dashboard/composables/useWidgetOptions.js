import { computed, watch } from 'vue'
import { useStore } from 'vuex'
import { resolveFormula } from '@baserow/modules/core/formula'
import { RuntimeFormulaContext } from '@baserow/modules/core/runtimeFormulaContext'

/** Resolve saved dropdown formulas reactively from the source context data. */
export function useWidgetOptions(props) {
  const store = useStore()
  const app = useNuxtApp()
  const optionState = computed(() => {
    if (props.widget.mode !== 'dropdown')
      return { values: [], loading: false, error: false }
    const prefix = props.storePrefix || ''
    if (store.getters[`${prefix}dashboardApplication/isLoading`])
      return { values: [], loading: true, error: false }
    try {
      const context = new Proxy(
        new RuntimeFormulaContext(
          {
            data_source_context: app.$registry.get(
              'dashboardDataProvider',
              'data_source_context'
            ),
          },
          { storePrefix: prefix }
        ),
        { get: (target, property) => target.get(property) }
      )
      const result = resolveFormula(
        props.widget.options || {},
        {
          get: (name) => app.$registry.get('runtimeFormulaFunction', name),
        },
        context
      )
      if (result === null && props.widget.options?.formula)
        throw new Error('Unresolvable filter options')
      const candidates =
        typeof result === 'string'
          ? result.split(',').map((value) => value.trim())
          : (result ?? [])
      if (
        !Array.isArray(candidates) ||
        candidates.some(
          (value) =>
            value !== null &&
            !['string', 'number', 'boolean'].includes(typeof value)
        )
      )
        throw new Error('Invalid filter options')
      return {
        values: [
          ...new Set(
            candidates
              .filter((value) => value !== null)
              .map(String)
              .filter((value) => value.trim())
          ),
        ],
        loading: false,
        error: false,
      }
    } catch {
      return { values: [], loading: false, error: true }
    }
  })
  const options = computed(() => optionState.value.values)
  let lastResolved
  watch(
    () => [props.widget.id, optionState.value],
    () => {
      if (
        optionState.value.loading ||
        optionState.value.error ||
        props.widget.mode !== 'dropdown'
      )
        return
      const signature = JSON.stringify([
        props.widget.id,
        props.widget.options,
        options.value,
      ])
      if (signature === lastResolved) return
      lastResolved = signature
      store.dispatch(
        `${props.storePrefix || ''}dashboardApplication/reconcileWidgetOptions`,
        { widgetId: props.widget.id, options: options.value }
      )
    },
    { immediate: true, deep: true }
  )
  return { optionState, options }
}
