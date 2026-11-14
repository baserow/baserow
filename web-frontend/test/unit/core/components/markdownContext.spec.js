import { mountSuspended } from '@nuxt/test-utils/runtime'
import MarkdownContext from '@baserow/modules/core/components/MarkdownContext'

const mountContext = (content) =>
  mountSuspended(MarkdownContext, {
    props: { title: 'Note', content },
    global: {
      stubs: { Context: { template: '<div><slot /></div>' } },
    },
  })

describe('MarkdownContext', () => {
  test('renders the content as markdown', async () => {
    const wrapper = await mountContext('Why **this** step')

    expect(wrapper.find('.markdown-context__title').text()).toBe('Note')
    expect(wrapper.find('strong').text()).toBe('this')
  })

  test('opens links in a new tab', async () => {
    const wrapper = await mountContext('[docs](https://baserow.io)')

    const link = wrapper.find('a')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  test('renders neither raw HTML nor images', async () => {
    const wrapper = await mountContext(
      '<b>bold</b> ![a <i>pixel</i>](https://example.com/pixel.png)'
    )

    expect(wrapper.find('b').exists()).toBe(false)
    expect(wrapper.find('i').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('.markdown-context__content').text()).toBe(
      '<b>bold</b> a <i>pixel</i>'
    )
  })
})
