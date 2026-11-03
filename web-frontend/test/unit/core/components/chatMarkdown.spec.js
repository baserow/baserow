import { afterEach, describe, expect, test, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { routerKey } from 'vue-router'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'

const { origin, pathname } = window.location
const appPaths = ['/database/', `${pathname}#`]

function render(content) {
  const router = {
    resolve: (path) => ({
      matched: appPaths.some((prefix) => path.startsWith(prefix)) ? [{}] : [],
    }),
    push: vi.fn(),
  }
  const open = vi.spyOn(window, 'open').mockImplementation(() => null)
  const wrapper = mount(ChatMarkdown, {
    props: { content },
    global: { provide: { [routerKey]: router } },
  })
  return { wrapper, link: wrapper.find('a'), router, open }
}

describe('ChatMarkdown', () => {
  afterEach(() => vi.restoreAllMocks())

  test('renders markdown without raw HTML or images', () => {
    const { wrapper } = render(
      '- **First**\n- ![leak](https://evil.test/?q=1)\n\n<img src="https://evil.test/?q=2" onerror="alert(1)">'
    )

    expect(wrapper.find('strong').text()).toBe('First')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  test.each([
    ['[Table](/database/1/table/2)', '/database/1/table/2'],
    ['[Setup](#setup)', `${pathname}#setup`],
  ])('opens %s in the app', async (content, path) => {
    const { link, router, open } = render(content)

    await link.trigger('click')

    expect(router.push).toHaveBeenCalledExactlyOnceWith(path)
    expect(open).not.toHaveBeenCalled()
  })

  test.each([
    `[File](${origin}/media/user_files/report.pdf)`,
    '[Site](https://example.com/page)',
  ])('opens %s in a new tab', async (content) => {
    const { link, router, open } = render(content)

    await link.trigger('click')

    expect(open).toHaveBeenCalledExactlyOnceWith(
      link.element.href,
      '_blank',
      'noopener,noreferrer'
    )
    expect(router.push).not.toHaveBeenCalled()
  })

  test.each([
    ['[Table](/database/1/table/2)', { metaKey: true }],
    ['Write to support@example.com', {}],
  ])('leaves %s to the browser', (content, modifiers) => {
    const { link, router, open } = render(content)
    const click = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      ...modifiers,
    })

    link.element.dispatchEvent(click)

    expect(click.defaultPrevented).toBe(false)
    expect(router.push).not.toHaveBeenCalled()
    expect(open).not.toHaveBeenCalled()
  })
})
