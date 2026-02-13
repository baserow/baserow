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
})
