import { describe, expect, test, vi } from 'vitest'
import { Registry } from '@baserow/modules/core/registry'
import {
  groupToolSteps,
  toolActivity,
  ToolPresentationType,
} from '@baserow/modules/core/toolPresentationTypes'
import en from '@baserow/modules/core/locales/en.json'
import { STEP_ERROR_CODE } from '@baserow/modules/core/chatRuns/constants'

const { createI18n } = await vi.importActual('vue-i18n')
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      ...en,
      testTool: { running: 'Sending an email', done: 'Email sent' },
    },
  },
  missingWarn: false,
  fallbackWarn: false,
})
const t = i18n.global.t

class EmailPresentation extends ToolPresentationType {
  static getType() {
    return 'send_email'
  }

  getActivity({ status }, translate) {
    return translate(`testTool.${status}`)
  }
}

function registryWith(Presenter) {
  const registry = new Registry()
  registry.registerNamespace('toolPresentation')
  registry.register(
    'toolPresentation',
    new Presenter({ app: { $i18n: i18n.global } })
  )
  return registry
}

describe('shared tool presentations', () => {
  test('a registered presenter describes its tool calls', () => {
    const registry = registryWith(EmailPresentation)
    const step = {
      id: 'email-1',
      tool: 'send_email',
      status: 'running',
      changes_data: false,
    }

    expect(toolActivity(step, registry, t)).toEqual({
      id: 'email-1',
      title: 'Sending an email',
      status: 'running',
      changesData: false,
      group: null,
      input: null,
      failureHint: '',
    })
    expect(groupToolSteps([step], registry, t)).toEqual([
      expect.objectContaining({ title: 'Sending an email', lines: [] }),
    ])
    expect(toolActivity({ ...step, status: 'done' }, registry, t).title).toBe(
      'Email sent'
    )
  })

  test.each(['running', 'done', 'failed', 'stopped'])(
    'unknown tools retain their %s status without exposing their data',
    (status) => {
      const registry = registryWith(EmailPresentation)
      const activity = toolActivity(
        {
          id: 'unknown',
          tool: '<img src=secret>',
          status,
          input: { target: 'secret', values: { password: 'secret' } },
          facts: { output: 'private result' },
        },
        registry,
        t
      )

      expect(activity.status).toBe(status)
      expect(activity.title).toBe(t(`toolPresentation.${status}`))
      expect(activity.group).toBe(null)
      expect(JSON.stringify(activity)).not.toContain('secret')
      expect(JSON.stringify(activity)).not.toContain('private result')
    }
  )

  test.each(['throws', 'missing translation', 'empty text'])(
    'a presenter that returns %s falls back without interrupting chat',
    (failure) => {
      class BrokenPresentation extends EmailPresentation {
        getActivity(step, translate) {
          if (failure === 'throws') throw new Error('Broken formatter')
          return failure === 'empty text' ? '' : translate('missing.tool.key')
        }
      }
      const registry = registryWith(BrokenPresentation)

      expect(
        toolActivity({ tool: 'send_email', status: 'done' }, registry, t)
      ).toMatchObject({ title: 'Tool completed', status: 'done', group: null })
    }
  )

  test('malformed steps and a failing translator still produce a safe activity', () => {
    const registry = registryWith(EmailPresentation)
    const unavailableTranslation = () => {
      throw new Error('Unavailable translations')
    }

    expect(toolActivity(null, registry, unavailableTranslation)).toMatchObject({
      title: 'Tool interrupted',
      status: 'stopped',
    })
    expect(groupToolSteps(null, registry, t)).toEqual([])
  })

  test('accepts a fallback-locale translation absent from the current locale', () => {
    const registry = registryWith(EmailPresentation)
    registry.get('toolPresentation', 'send_email').app = {
      $i18n: { te: () => false },
    }

    expect(
      toolActivity({ tool: 'send_email', status: 'running' }, registry, t).title
    ).toBe('Sending an email')
  })

  test('input previews require the presenter to opt in', () => {
    const registry = registryWith(EmailPresentation)
    const step = {
      tool: 'send_email',
      status: 'done',
      input: { values: { subject: 'Hello' }, truncated: true },
    }
    expect(toolActivity(step, registry, t).input).toBe(null)

    registry.get('toolPresentation', 'send_email').getInput = ({ input }) =>
      input
    expect(toolActivity(step, registry, t).input).toEqual(step.input)
  })

  test.each([null, {}, { values: [] }, { values: 'secret' }, { values: {} }])(
    'omits malformed or empty input previews: %j',
    (input) => {
      const registry = registryWith(EmailPresentation)
      registry.get('toolPresentation', 'send_email').getInput = () => input
      expect(
        toolActivity({ tool: 'send_email', status: 'done' }, registry, t)
      ).toMatchObject({ title: 'Email sent', input: null })
    }
  )

  test('broken, circular and oversized previews leave the activity usable', () => {
    const registry = registryWith(EmailPresentation)
    const presenter = registry.get('toolPresentation', 'send_email')
    const circular = {}
    circular.self = circular
    for (const getInput of [
      () => {
        throw new Error('Broken preview')
      },
      () => ({ values: circular }),
      () => ({ values: { body: 'x'.repeat(40000) } }),
    ]) {
      presenter.getInput = getInput
      expect(
        toolActivity({ tool: 'send_email', status: 'done' }, registry, t)
      ).toMatchObject({ title: 'Email sent', input: null })
    }
  })

  test.each([
    [STEP_ERROR_CODE.NOT_FOUND, 'Not found or not accessible to the agent.'],
    [
      STEP_ERROR_CODE.PERMISSION_DENIED,
      'Permission denied for this operation.',
    ],
    [STEP_ERROR_CODE.INVALID_INPUT, 'The tool received invalid input.'],
    [STEP_ERROR_CODE.FAILED, 'This tool call failed.'],
  ])(
    'translates the shared failure code %s even for an unknown presenter',
    (code, hint) => {
      const registry = registryWith(EmailPresentation)
      expect(
        toolActivity(
          { tool: 'future_action', status: 'failed', error_code: code },
          registry,
          t
        ).failureHint
      ).toBe(hint)
    }
  )

  test.each([
    undefined,
    null,
    {},
    ['not_found'],
    '__proto__',
    '<script>private</script>',
  ])('unknown or missing failure codes use a generic hint: %j', (errorCode) => {
    const registry = registryWith(EmailPresentation)
    expect(
      toolActivity(
        {
          tool: 'send_email',
          status: 'failed',
          error_code: errorCode,
          error: 'PRIVATE_EXCEPTION',
          facts: { error: 'PRIVATE_RESULT' },
        },
        registry,
        t
      ).failureHint
    ).toBe('This tool call failed.')
  })

  test.each(['running', 'done', 'stopped'])(
    'ignores stale failure codes when status is %s',
    (status) => {
      expect(
        toolActivity(
          { tool: 'send_email', status, error_code: STEP_ERROR_CODE.NOT_FOUND },
          registryWith(EmailPresentation),
          t
        ).failureHint
      ).toBe('')
    }
  )

  test('a missing failure translation falls back without exposing the key', () => {
    expect(
      toolActivity(
        {
          tool: 'send_email',
          status: 'failed',
          error_code: STEP_ERROR_CODE.NOT_FOUND,
        },
        registryWith(EmailPresentation),
        (key) => key
      ).failureHint
    ).toBe('This tool call failed.')
  })

  test('future action presenters can name a failure target through the shared hint', () => {
    class TargetedEmail extends EmailPresentation {
      getActivity() {
        return 'Send email'
      }

      getTarget({ input }) {
        return input.target
      }
    }
    const registry = registryWith(TargetedEmail)
    const step = {
      tool: 'send_email',
      status: 'failed',
      error_code: STEP_ERROR_CODE.PERMISSION_DENIED,
      input: { target: 'alice@example.com' },
    }
    expect(toolActivity(step, registry, t)).toMatchObject({
      title: 'Send email',
      failureHint: 'Permission denied for this operation on alice@example.com.',
    })

    registry.get('toolPresentation', 'send_email').getTarget = () => {
      throw new Error('Broken target formatter')
    }
    expect(toolActivity(step, registry, t)).toMatchObject({
      title: 'Send email',
      failureHint: 'Permission denied for this operation.',
    })
  })

  test.each([null, {}, [], ' ', 'x'.repeat(1025)])(
    'malformed or oversized target hints use the generic reason: %j',
    (target) => {
      class TargetedEmail extends EmailPresentation {
        getActivity() {
          return 'Send email'
        }
        getTarget() {
          return target
        }
      }
      expect(
        toolActivity(
          {
            tool: 'send_email',
            status: 'failed',
            error_code: STEP_ERROR_CODE.NOT_FOUND,
          },
          registryWith(TargetedEmail),
          t
        ).failureHint
      ).toBe('Not found or not accessible to the agent.')
    }
  )
})
