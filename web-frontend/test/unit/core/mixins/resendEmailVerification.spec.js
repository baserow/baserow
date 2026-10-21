import resendEmailVerification from '@baserow/modules/core/mixins/resendEmailVerification'

describe('resendEmailVerification mixin', () => {
  const { resend } = resendEmailVerification.methods

  test('shows a toast when the request is throttled', async () => {
    const handler = {
      isTooManyRequests: () => true,
      getMessage: () => ({ title: 'Too many requests', message: 'Wait' }),
      handled: vi.fn(),
    }
    const context = {
      resendLoading: false,
      resendSuccess: false,
      $client: { post: vi.fn().mockRejectedValue({ handler }) },
      $store: { dispatch: vi.fn() },
      $t: (key) => key,
    }

    await resend.call(context, 'test@example.com')

    expect(context.$store.dispatch).toHaveBeenCalledWith('toast/error', {
      title: 'Too many requests',
      message: 'Wait',
    })
    expect(handler.handled).toHaveBeenCalled()
    expect(context.resendSuccess).toBe(false)
    expect(context.resendLoading).toBe(false)
  })
})
