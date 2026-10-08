import { h } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import FormulaInputExplorerContext from '@baserow/modules/core/components/formula/FormulaInputExplorerContext.vue'

// The real Context only renders its content once it has been opened. A
// pass-through stub shows the footer straight away, which is all that is
// being checked here.
const ContextStub = {
  name: 'Context',
  render() {
    return h('div', { class: 'context' }, this.$slots.default?.())
  },
}

const mountContext = (props) =>
  mountSuspended(FormulaInputExplorerContext, {
    props: { nodesHierarchy: [], ...props },
    global: {
      stubs: {
        Context: ContextStub,
        NodeExplorer: true,
        FormulaInputModeChangeModal: true,
      },
    },
  })

const footer = (wrapper) =>
  wrapper.find('.formula-input-explorer-context__footer')

describe('FormulaInputExplorerContext', () => {
  test('offers the mode toggle when both modes are enabled', async () => {
    const wrapper = await mountContext({
      mode: 'advanced',
      enabledModes: ['simple', 'advanced'],
    })

    expect(footer(wrapper).exists()).toBe(true)
    expect(footer(wrapper).text()).toBe(
      'formulaInputExplorerContext.useSimpleInput'
    )
  })

  test('the toggle switches to the other mode', async () => {
    const wrapper = await mountContext({
      mode: 'advanced',
      enabledModes: ['simple', 'advanced'],
    })

    await footer(wrapper).find('.button-text').trigger('click')

    expect(wrapper.emitted('mode-changed')).toEqual([['simple']])
  })

  test.each([['advanced'], ['simple']])(
    'has nothing to switch to when only %s is enabled',
    async (mode) => {
      const wrapper = await mountContext({ mode, enabledModes: [mode] })

      expect(footer(wrapper).exists()).toBe(false)
    }
  )
})
