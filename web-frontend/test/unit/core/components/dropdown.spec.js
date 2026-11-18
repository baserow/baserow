import { flushPromises } from '@vue/test-utils'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Dropdown component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({ props = {}, listeners = {}, slots = {} } = {}) => {
    return testApp.mount(Dropdown, { props: props, listeners, slots })
  }

  test('basics', async () => {
    const wrapper = await mountComponent()
    expect(wrapper.element).toMatchSnapshot()

    const wrapper2 = await mountComponent({ props: { showSearch: false } })
    expect(wrapper2.element).toMatchSnapshot()

    const wrapper3 = await mountComponent({ props: { disabled: true } })
    expect(wrapper3.element).toMatchSnapshot()
  })

  test('With items', async () => {
    const wrapper = await mountComponent({
      slots: {
        default: `<DropdownItem value="a" name="A"/>`,
      },
    })
    expect(wrapper.element).toMatchSnapshot()

    const wrapper2 = await mountComponent({
      props: { value: 'a' },
      slots: {
        default: `<DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>
          <DropdownItem value="c" name="C" :disabled="true"/>
          <DropdownItem value="d" name="D" icon="times"/>
          <DropdownItem value="e" name="E" description="My description"/>
          `,
      },
    })
    expect(wrapper2.element).toMatchSnapshot()

    const wrapper3 = await mountComponent({
      props: { value: 'a', showInput: false },
      slots: {
        default: `<DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>
          `,
      },
    })
    expect(wrapper3.element).toMatchSnapshot()
  })

  test('slots', async () => {
    const wrapper = await mountComponent({
      props: { value: 'a' },
      slots: {
        default: `<DropdownItem value="a" name="A">My item</DropdownItem>`,
        value: `<p>The value</p>`,
      },
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('change value prop', async () => {
    const wrapper = await mountComponent({
      props: { value: 'a' },
      slots: {
        default: `<DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>`,
      },
    })

    wrapper.setProps({ value: 'b' })
    await wrapper.vm.$nextTick()
    expect(wrapper.element).toMatchSnapshot()
  })

  test('multiple selection handles an undefined value', async () => {
    const wrapper = await mountComponent({
      props: { modelValue: ['a'], multiple: true },
      slots: {
        default: `<DropdownItem value="a" name="A"/>`,
      },
    })

    expect(wrapper.find('.dropdown__selected-text').text()).toBe('A')

    await wrapper.setProps({ modelValue: undefined })

    expect(wrapper.find('.dropdown__selected-placeholder').exists()).toBe(true)
  })

  test('interactions', async () => {
    let wrapper = null

    const onInput = vi.fn(async (newVal) => {
      wrapper.setProps({ value: newVal })
      await wrapper.vm.$nextTick()
    })

    wrapper = await mountComponent({
      props: { value: 'a' },
      slots: {
        default: `<DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>`,
      },
      listeners: { input: onInput },
    })

    await wrapper.find('.dropdown__selected').trigger('click')

    expect(wrapper.element).toMatchSnapshot()

    await wrapper
      .find('.select__items :nth-child(1)')
      .find('.select__item-link')
      .trigger('click')

    await wrapper.vm.$nextTick()

    expect(onInput).toHaveBeenCalledWith('a')

    expect(wrapper.element).toMatchSnapshot()
  })

  test('clearable single select clears when choosing the active value', async () => {
    let wrapper = null

    const onInput = vi.fn(async (newVal) => {
      wrapper.setProps({ value: newVal })
      await wrapper.vm.$nextTick()
    })

    wrapper = await mountComponent({
      props: { value: 'a', clearable: true },
      slots: {
        default: `<DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>`,
      },
      listeners: { input: onInput },
    })

    await wrapper.find('.dropdown__selected').trigger('click')
    await wrapper
      .find('.select__items :nth-child(1)')
      .find('.select__item-link')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(onInput).toHaveBeenLastCalledWith(null)
  })

  test('focus', async () => {
    let wrapper = null

    const onInput = vi.fn(async (newVal) => {
      wrapper.setProps({ value: newVal })
      await wrapper.vm.$nextTick()
    })

    wrapper = await mountComponent({
      props: { value: 'a' },
      slots: {
        default: `<DropdownItem value="a" name="A"/>`,
      },
      listeners: { input: onInput },
    })

    await wrapper.find('.dropdown').trigger('focusin')

    expect(wrapper.element).toMatchSnapshot()

    await wrapper
      .find('.dropdown')
      .trigger('focusout', { relatedTarget: document.createElement('div') })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('children', async () => {
    let wrapper = await mountComponent()
    let children = await wrapper.vm.getDropdownItemComponents()
    expect(children).toEqual([])

    wrapper = await mountComponent({
      slots: {
        default: `
          <DropdownItem value="a" name="A"/>
          <DropdownItem value="b" name="B"/>
          <DropdownItem value="c" name="C"/>
          <DropdownItem value="d" name="D"/>
        `,
      },
    })
    children = await wrapper.vm.getDropdownItemComponents()
    expect(children.length).toEqual(4)

    wrapper = await mountComponent({
      slots: {
        default: `
          <div id="group-1">
            <DropdownItem value="a" name="A"/>
            <DropdownItem value="b" name="B"/>
          </div>
          <div id="group-2">
            <DropdownItem value="c" name="C"/>
            <DropdownItem value="d" name="D"/>
          </div>
        `,
      },
    })
    children = await wrapper.vm.getDropdownItemComponents()
    expect(children.length).toEqual(4)
  })

  describe('fixed menu placement', () => {
    let viewportHeight

    beforeEach(() => {
      viewportHeight = vi
        .spyOn(window, 'innerHeight', 'get')
        .mockReturnValue(800)
    })

    afterEach(() => vi.restoreAllMocks())

    const mockMenuHeight = (wrapper, scrollHeight = 300) => {
      const menu = wrapper.find('.dropdown__items').element
      const items = wrapper.find('.select__items').element
      // The list is constrained, but search and footer still take up 120px.
      vi.spyOn(menu, 'offsetHeight', 'get').mockReturnValue(160)
      vi.spyOn(items, 'clientHeight', 'get').mockReturnValue(40)
      vi.spyOn(items, 'scrollHeight', 'get').mockReturnValue(scrollHeight)
      return menu
    }

    const openFloatingMenu = async ({ top = 560, scrollHeight = 300 } = {}) => {
      const wrapper = await testApp.mount({
        components: { Dropdown },
        template: `
          <div>
            <button @click="$refs.dropdown.show($event.currentTarget)">Add options</button>
            <Dropdown ref="dropdown" :show-input="false" :tabindex="-1" fixed-items show-footer>
              <DropdownItem value="a" name="A" />
              <DropdownItem value="b" name="B" />
              <template #footer><button>Apply</button></template>
            </Dropdown>
          </div>
        `,
      })
      vi.spyOn(
        wrapper.find('button').element,
        'getBoundingClientRect'
      ).mockReturnValue(new DOMRect(120, top, 280, 36))
      vi.spyOn(
        wrapper.find('.dropdown').element,
        'getBoundingClientRect'
      ).mockReturnValue(new DOMRect(40, 650, 100, 0))
      const menu = mockMenuHeight(wrapper, scrollHeight)
      await wrapper.find('button').trigger('click')
      await flushPromises()
      return menu
    }

    test('opens above an external button when the full list and footer do not fit below, and repositions after resize', async () => {
      // 184px remains below the button: more than the old 140px threshold.
      const menu = await openFloatingMenu()
      expect(menu.style.left).toBe('120px')
      expect(menu.style.minWidth).toBe('280px')
      expect(menu.style.top).toBe('auto')
      expect(menu.style.bottom).toBe('240px')
      expect(menu.style.maxHeight).toBe('540px')

      viewportHeight.mockReturnValue(1100)
      window.dispatchEvent(new Event('resize'))
      expect(menu.style.top).toBe('596px')
      expect(menu.style.bottom).toBe('auto')
      expect(menu.style.maxHeight).toBe('484px')
    })

    test('opens below an external button when there is enough space', async () => {
      const menu = await openFloatingMenu({ top: 80 })
      expect(menu.style.top).toBe('116px')
      expect(menu.style.bottom).toBe('auto')
      expect(menu.style.maxHeight).toBe('664px')
    })

    test('keeps a short menu below the button even when there is more space above', async () => {
      const menu = await openFloatingMenu({ scrollHeight: 40 })
      expect(menu.style.top).toBe('596px')
      expect(menu.style.bottom).toBe('auto')
      expect(menu.style.maxHeight).toBe('184px')
    })

    test('preserves the inline fixed dropdown alignment and minimum-height threshold', async () => {
      const wrapper = await mountComponent({
        props: { fixedItems: true, showFooter: true },
        slots: {
          default: '<DropdownItem value="a" name="A" />',
          footer: '<button>Apply</button>',
        },
      })
      vi.spyOn(wrapper.element, 'getBoundingClientRect').mockReturnValue(
        new DOMRect(40, 560, 320, 36)
      )
      const menu = mockMenuHeight(wrapper)
      await wrapper.find('.dropdown__selected').trigger('click')
      await flushPromises()
      expect(menu.style.left).toBe('40px')
      expect(menu.style.minWidth).toBe('320px')
      expect(menu.style.top).toBe('560px')
      expect(menu.style.bottom).toBe('auto')
      expect(menu.style.maxHeight).toBe('calc(100vh - 580px)')
    })
  })
})
