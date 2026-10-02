import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

describe('AI field card', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new PremiumTestApp()
    await testApp.getStore().dispatch('workspace/forceCreate', {
      id: 1,
      name: 'testWorkspace',
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountCard = (field, value) =>
    testApp.mount(
      testApp.getRegistry().get('field', field.type).getCardComponent(field),
      { props: { field, value, workspaceId: 1, row: { id: 1 } } }
    )

  test('renders a rich text AI value without mentions or images', async () => {
    const wrapper = await mountCard(
      {
        id: 1,
        type: 'ai',
        ai_output_type: 'text',
        long_text_enable_rich_text: true,
      },
      '**bold** @5 ![a](https://example.com/a.png)'
    )

    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.find('.rich-text-editor__mention').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.iconoir-media-image').exists()).toBe(false)
    expect(wrapper.text()).toBe('bold @5 ![a](https://example.com/a.png)')
  })

  test('still resolves mentions in a rich long text value', async () => {
    const wrapper = await mountCard(
      { id: 2, type: 'long_text', long_text_enable_rich_text: true },
      '**bold** @5'
    )

    expect(wrapper.find('.rich-text-editor__mention').text()).toBe('@Jane Doe')
  })

  test.each([
    [
      'plain text',
      {
        id: 3,
        type: 'ai',
        ai_output_type: 'text',
        long_text_enable_rich_text: false,
      },
      'Yes',
    ],
    [
      'choice',
      {
        id: 4,
        type: 'ai',
        ai_output_type: 'choice',
        long_text_enable_rich_text: true,
        select_options: [{ id: 1, value: 'Yes', color: 'green' }],
      },
      { id: 1, value: 'Yes', color: 'green' },
    ],
  ])(
    'passes no rich text props to the %s output card',
    async (outputName, field, value) => {
      const wrapper = await mountCard(field, value)

      expect(wrapper.text()).toBe('Yes')
      expect(wrapper.html()).not.toMatch(/enable-?(mentions|images)/i)
    }
  )
})
