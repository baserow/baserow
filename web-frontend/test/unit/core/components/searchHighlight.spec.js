import { shallowMount } from '@vue/test-utils'
import SearchHighlight from '@baserow/modules/core/components/SearchHighlight'

describe('SearchHighlight.vue', () => {
  it('renders the plain text without marks when the query is empty', () => {
    const wrapper = shallowMount(SearchHighlight, {
      propsData: { text: 'Marketing', query: '' },
    })
    expect(wrapper.text()).toBe('Marketing')
    expect(wrapper.findAll('mark')).toHaveLength(0)
  })

  it('wraps the case insensitive match in a mark element', () => {
    const wrapper = shallowMount(SearchHighlight, {
      propsData: { text: 'Marketing', query: 'mark' },
    })
    const marks = wrapper.findAll('mark')
    expect(marks).toHaveLength(1)
    expect(marks[0].text()).toBe('Mark')
    expect(wrapper.text()).toBe('Marketing')
  })

  it('highlights every occurrence of the query', () => {
    const wrapper = shallowMount(SearchHighlight, {
      propsData: { text: 'Test workflow test', query: 'test' },
    })
    expect(wrapper.findAll('mark')).toHaveLength(2)
  })
})
