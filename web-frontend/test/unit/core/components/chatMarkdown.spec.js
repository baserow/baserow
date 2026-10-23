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
  const wrapper = mount(ChatMarkdown, {
    props: { content },
    global: { provide: { [routerKey]: router } },
  })
  return { link: wrapper.get('a'), router }
}

describe('ChatMarkdown', () => {
  afterEach(() => vi.restoreAllMocks())

  test.each([
    ['[Table](/database/1/table/2)', '/database/1/table/2'],
    ['[Setup](#setup)', `${pathname}#setup`],
  ])('opens %s in the app', async (content, path) => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { link, router } = render(content)

    await link.trigger('click')

    expect(router.push).toHaveBeenCalledExactlyOnceWith(path)
    expect(open).not.toHaveBeenCalled()
  })

  test.each([
    `[File](${origin}/media/user_files/report.pdf)`,
    '[Site](https://example.com/page)',
  ])('opens %s in a new tab', async (content) => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { link, router } = render(content)

    await link.trigger('click')

    expect(open).toHaveBeenCalledExactlyOnceWith(
      link.element.href,
      '_blank',
      'noopener,noreferrer'
    )
    expect(router.push).not.toHaveBeenCalled()
  })

  test('leaves clicks with a modifier key to the browser', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { link, router } = render('[Table](/database/1/table/2)')
    const click = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      metaKey: true,
    })

    link.element.dispatchEvent(click)

    expect(click.defaultPrevented).toBe(false)
    expect(router.push).not.toHaveBeenCalled()
    expect(open).not.toHaveBeenCalled()
  })
})
