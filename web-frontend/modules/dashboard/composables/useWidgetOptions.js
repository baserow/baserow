import { computed, onMounted, watch } from 'vue'
import { useStore } from 'vuex'

export function useWidgetOptions(props) {
  const store = useStore()
  const optionState = computed(() => {
    const cached =
      store.getters[
        `${props.storePrefix}dashboardApplication/getWidgetOptions`
      ][props.widget.id]
    return cached && cached.signature === JSON.stringify(props.widget.options)
      ? cached
      : { values: [], loading: true, error: false }
  })
  const options = computed(() => optionState.value.values)
  const loadOptions = (force = false) =>
    props.widget.mode === 'dropdown' &&
    store.dispatch(
      `${props.storePrefix}dashboardApplication/fetchWidgetOptions`,
      { widgetId: props.widget.id, force }
    )
  onMounted(() => loadOptions())
  watch(
    () => [
      props.widget.id,
      props.widget.mode,
      JSON.stringify(props.widget.options),
    ],
    () => loadOptions()
  )
  return { optionState, options, loadOptions }
}
