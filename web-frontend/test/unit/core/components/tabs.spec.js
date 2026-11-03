import { mount } from '@vue/test-utils'
import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'

import { mountSuspended } from '@nuxt/test-utils/runtime'

describe('Tabs', () => {
  it('renders the correct number of tabs', async () => {
    const tabs = [
      { title: 'Tab 1', content: 'Tab 1 content' },
      { title: 'Tab 2', content: 'Tab 2 content' },
      { title: 'Tab 3', content: 'Tab 3 content' },
    ]

    const wrapper = await mountSuspended(Tabs, {
      components: {
        Tab,
      },
      slots: {
        default: tabs
          .map((tab) => `<Tab title="${tab.title}">${tab.content}</Tab>`)
          .join(''),
      },
    })

    expect(wrapper.findAllComponents(Tab).length).toEqual(tabs.length)
  })

  it('emits a tab-selected event when a tab is clicked', async () => {
    const tabs = [
      { title: 'Tab 1', content: 'Tab 1 content' },
      { title: 'Tab 2', content: 'Tab 2 content' },
      { title: 'Tab 3', content: 'Tab 3 content' },
    ]

    const wrapper = await mountSuspended(Tabs, {
      components: {
        Tab,
      },
      slots: {
        default: tabs
          .map((tab) => `<Tab title="${tab.title}">${tab.content}</Tab>`)
          .join(''),
      },
    })

    await wrapper.vm.$nextTick()
    wrapper.vm.selectTab(1)

    expect(wrapper.emitted('update:selectedIndex')).toBeTruthy()
  })

  it('does not render guided tour highlights as tab content', async () => {
    const wrapper = await mountSuspended(Tabs, {
      components: {
        Tab,
      },
      slots: {
        default: '<Tab title="Agents" highlight="tour-target">Content</Tab>',
      },
    })

    const tabItem = wrapper.get('.tabs__item')
    expect(tabItem.attributes('data-highlight')).toBe('tour-target')
    expect(tabItem.get('.tabs__link').text()).toBe('Agents')
  })

  it.each(['', 'badge="New"'])(
    'renders one development badge when the tab also has %s',
    async (badge) => {
      const wrapper = await mountSuspended(Tabs, {
        components: {
          Tab,
        },
        slots: {
          default: `<Tab title="Agents" development-stage="beta" ${badge}>Content</Tab>`,
        },
      })

      expect(wrapper.findAll('.tabs__link .badge')).toHaveLength(1)
      expect(wrapper.get('.tabs__link .badge').text()).toContain('common.beta')
    }
  )
})

test('shows an optional tab badge without changing its navigation label', async () => {
  const wrapper = await mountSuspended(Tabs, {
    slots: {
      default:
        '<Tab title="Members">Members</Tab><Tab title="Agents" badge="New">Agents</Tab>',
    },
  })
  const links = wrapper.findAll('.tabs__link')
  expect(links[0].find('.badge').exists()).toBe(false)
  expect(links[1].get('.badge').text()).toBe('New')
  await links[1].trigger('click')
  expect(wrapper.get('.tabs__item--active').text()).toContain('Agents')
  wrapper.unmount()
})

test('updates tab item badges while preserving the selected tab and default color', async () => {
  const wrapper = await mountSuspended(Tabs, {
    props: {
      tabItems: [
        { title: 'With a value', badge: '0', badgeColor: 'neutral' },
        { title: 'When empty', badge: '0' },
      ],
    },
  })
  expect(wrapper.findAll('.badge').map((badge) => badge.text())).toEqual([
    '0',
    '0',
  ])
  expect(wrapper.findAll('.badge')[0].classes()).toContain('badge--neutral')
  expect(wrapper.findAll('.badge')[1].classes()).toContain('badge--cyan')
  await wrapper.findAll('.tabs__link')[1].trigger('click')
  await wrapper.setProps({
    tabItems: [
      { title: 'With a value', badge: '2', badgeColor: 'neutral' },
      { title: 'When empty', badge: '1' },
    ],
  })
  expect(wrapper.findAll('.badge').map((badge) => badge.text())).toEqual([
    '2',
    '1',
  ])
  expect(wrapper.get('.tabs__item--active').text()).toContain('When empty')
  wrapper.unmount()
})
