// composables/useElementRuntime.js
import { computed, inject, toRef, isRef, ref, unref } from 'vue'
import { useNuxtApp } from '#app'
import { resolveColor } from '@baserow/modules/core/utils/colors'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'
import { useResolveFormula } from './useResolveFormula'
import { useApplicationContext } from './useApplicationContext'

export function useElement(props) {
  const { $store, $registry } = useNuxtApp()

  const { element } = props

  const { applicationContext } = useApplicationContext(props)
  const { resolveFormula } = useResolveFormula({ applicationContext })

  const workspace = inject('workspace')
  const builder = inject('builder')
  const currentPage = inject('currentPage')
  const elementPage = inject('elementPage')
  const mode = inject('mode')

  const elementType = computed(() => {
    const el = unref(element)
    if (!el) {
      return null
    }
    return $registry.get('element', el.type)
  })

  const workflowActionsInProgress = computed(() => {
    const el = unref(element)
    const elType = unref(elementType)
    if (!el || !elType) {
      return false
    }

    const workflowActions = $store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](unref(elementPage), el.id)

    const dispatchedById = elType.uniqueElementId({
      element: el,
      applicationContext,
    })

    return workflowActions.some((workflowAction) =>
      $store.getters['builderWorkflowAction/getDispatching'](
        workflowAction,
        dispatchedById
      )
    )
  })

  const isEditMode = computed(() => unref(mode) === 'editing')

  const elementIsInError = computed(() => {
    const el = unref(element)
    const elType = unref(elementType)
    if (!el || !elType) {
      return false
    }
    return elType.isInError(el, applicationContext)
  })

  const themeConfigBlocks = computed(() =>
    $registry.getOrderedList('themeConfigBlock')
  )

  const colorVariables = computed(() =>
    ThemeConfigBlockType.getAllColorVariables(
      unref(themeConfigBlocks),
      unref(builder)?.theme
    )
  )

  async function fireEvent(event) {
    if (unref(mode) === 'editing') {
      return
    }

    if (unref(workflowActionsInProgress)) {
      return false
    }

    const el = unref(element)
    if (!el) {
      return
    }

    const workflowActions = $store.getters[
      'builderWorkflowAction/getElementWorkflowActions'
    ](unref(elementPage), el.id).filter(
      ({ event: eventName }) => eventName === event.name
    )

    await event.fire({
      workflowActions,
      resolveFormula,
      applicationContext,
    })
  }

  function getStyleOverride(key, overrideColorVariables = null) {
    const el = unref(element)
    if (!el) {
      return {}
    }

    return ThemeConfigBlockType.getAllStyles(
      unref(themeConfigBlocks),
      el.styles?.[key] || {},
      overrideColorVariables || unref(colorVariables),
      unref(builder)?.theme
    )
  }

  return {
    element,
    applicationContext,
    resolveFormula,

    // context (if you need them in the component)
    workspace,
    builder,
    currentPage,
    elementPage,
    mode,

    // computed equivalents
    workflowActionsInProgress,
    elementType,
    isEditMode,
    elementIsInError,
    themeConfigBlocks,
    colorVariables,

    // methods
    fireEvent,
    getStyleOverride,
    resolveColor,
  }
}
