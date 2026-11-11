import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount } from '@vue/test-utils'
import { useNuxtApp } from '#app'

import TemplateList from '@baserow/modules/core/components/template/TemplateList'

const template = (id, name, keywords = '', description = '') => ({
  id,
  name,
  slug: name.toLowerCase().replace(/ /g, '-'),
  description,
  icon: 'iconoir-table',
  keywords,
})

const categories = [
  {
    id: 1,
    name: 'Business',
    templates: [
      template(1, 'Project Tracker', 'tasks,planning', 'Track projects.'),
      template(2, 'Applicant Tracker', 'hiring'),
    ],
  },
  {
    id: 2,
    name: 'Personal',
    templates: [template(3, 'Recipe Book', 'cooking')],
  },
]

// Mounted lists keep listening to the search shortcut.
enableAutoUnmount(afterEach)

async function mountComponent(props = {}) {
  return await mountSuspended(TemplateList, {
    attachTo: document.body,
    props: { categories, ...props },
    global: {
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

const sectionTitles = (wrapper) =>
  wrapper.findAll('.template-list__section-title').map((el) => el.text())

const cardNames = (wrapper) =>
  wrapper.findAll('.template-list__card-name').map((el) => el.text())

describe('TemplateList', () => {
  test('shows every category as a section of template cards', async () => {
    const wrapper = await mountComponent()

    expect(sectionTitles(wrapper)).toStrictEqual(['Business', 'Personal'])
    expect(cardNames(wrapper)).toStrictEqual([
      'Project Tracker',
      'Applicant Tracker',
      'Recipe Book',
    ])
  })

  test('shows the description only on cards that have one', async () => {
    const wrapper = await mountComponent()

    const cards = wrapper.findAll('.template-list__card')
    expect(cards[0].find('.template-list__card-description').text()).toBe(
      'Track projects.'
    )
    expect(cards[1].find('.template-list__card-description').exists()).toBe(
      false
    )
  })

  test('shows only the selected category', async () => {
    const wrapper = await mountComponent()

    const links = wrapper.findAll('.template-list__category-link')
    await links[2].trigger('click')

    expect(sectionTitles(wrapper)).toStrictEqual(['Personal'])

    await links[0].trigger('click')

    expect(sectionTitles(wrapper)).toStrictEqual(['Business', 'Personal'])
  })

  test('filters templates by name and keywords', async () => {
    const wrapper = await mountComponent()

    await wrapper.find('input').setValue('track')
    expect(cardNames(wrapper)).toStrictEqual([
      'Project Tracker',
      'Applicant Tracker',
    ])
    expect(sectionTitles(wrapper)).toStrictEqual(['Business'])

    await wrapper.find('input').setValue('cooking')
    expect(cardNames(wrapper)).toStrictEqual(['Recipe Book'])

    await wrapper.find('input').setValue('nothing matches')
    expect(cardNames(wrapper)).toStrictEqual([])
    expect(wrapper.find('.template-list__empty').text()).toBe(
      'templateCategories.noResults'
    )
  })

  test('collapses a section', async () => {
    const wrapper = await mountComponent()

    await wrapper.findAll('.template-list__section-title')[0].trigger('click')

    expect(cardNames(wrapper)).toStrictEqual(['Recipe Book'])
  })

  test('emits the clicked template', async () => {
    const wrapper = await mountComponent()

    await wrapper.findAll('.template-list__card')[2].trigger('click')

    expect(wrapper.emitted('selected')).toStrictEqual([
      [categories[1].templates[0]],
    ])
  })

  test('opens a template and a category with the keyboard', async () => {
    const wrapper = await mountComponent()

    const card = wrapper.findAll('.template-list__card')[0]
    expect(card.attributes('tabindex')).toBe('0')
    await card.trigger('keydown', { key: 'Enter' })
    await card.trigger('keydown', { key: ' ' })

    expect(wrapper.emitted('selected')).toStrictEqual([
      [categories[0].templates[0]],
      [categories[0].templates[0]],
    ])

    await wrapper
      .findAll('.template-list__category-link')[2]
      .trigger('keydown', { key: 'Enter' })

    expect(sectionTitles(wrapper)).toStrictEqual(['Personal'])
  })

  describe('search shortcut', () => {
    let otherListener = null

    beforeEach(() => {
      const { $priorityBus } = useNuxtApp()
      otherListener = vi.fn()
      $priorityBus.$on('start-search', $priorityBus.level.LOW, otherListener)
    })

    afterEach(() => {
      useNuxtApp().$priorityBus.$off('start-search', otherListener)
    })

    const startSearch = () =>
      useNuxtApp().$priorityBus.$emit('start-search', {
        event: { preventDefault: vi.fn() },
      })

    test('focuses the search input', async () => {
      const wrapper = await mountComponent()

      startSearch()

      expect(otherListener).not.toHaveBeenCalled()
      expect(document.activeElement).toBe(wrapper.find('input').element)
    })

    test('leaves the shortcut to others while inactive', async () => {
      const wrapper = await mountComponent({ active: false })

      startSearch()
      expect(otherListener).toHaveBeenCalledTimes(1)

      await wrapper.setProps({ active: true })
      startSearch()
      expect(otherListener).toHaveBeenCalledTimes(1)

      await wrapper.setProps({ active: false })
      startSearch()
      expect(otherListener).toHaveBeenCalledTimes(2)
    })
  })
})
