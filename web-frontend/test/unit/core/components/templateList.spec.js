import { mountSuspended } from '@nuxt/test-utils/runtime'

import TemplateList from '@baserow/modules/core/components/template/TemplateList'

const template = (id, name, keywords = '') => ({
  id,
  name,
  slug: name.toLowerCase().replace(/ /g, '-'),
  icon: 'iconoir-table',
  keywords,
})

const categories = [
  {
    id: 1,
    name: 'Business',
    templates: [
      template(1, 'Project Tracker', 'tasks,planning'),
      template(2, 'Applicant Tracker', 'hiring'),
    ],
  },
  {
    id: 2,
    name: 'Personal',
    templates: [template(3, 'Recipe Book', 'cooking')],
  },
]

async function mountComponent() {
  return await mountSuspended(TemplateList, {
    props: { categories },
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
    expect(wrapper.find('.template-list__empty').exists()).toBe(true)
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
})
