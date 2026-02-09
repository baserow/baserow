import {
  ClientErrorMap,
  makeErrorResponseInterceptor,
  ResponseErrorMessage,
} from '@baserow/modules/core/plugins/clientHandler'

function errorInterceptorWithStubAppAndStore(
  storeDispatches = [],
  errorPageData = {}
) {
  const stubApp = {
    $i18n: {
      t(t) {
        return t
      },
    },
  }
  return makeErrorResponseInterceptor(
    {
      dispatch(action, ...args) {
        storeDispatches.push({
          action,
          args,
        })
      },
    },
    stubApp,
    new ClientErrorMap(stubApp),
    ({ statusCode, message }) => {
      errorPageData.statusCode = statusCode
      errorPageData.message = message
    }
  )
}

describe('test error handling', () => {
  test(
    'test an 500 response with error and detail body attributes matches against' +
      ' corresponding specificErrorMap entry',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'matchesASpecificErrorCode',
              detail: 'detail',
            },
            status: 500,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage('name', {
          matchesASpecificErrorCode: new ResponseErrorMessage(
            'title',
            'message'
          ),
        })
        expect(message.title).toBe('title')
        expect(message.message).toBe('message')
      }
    }
  )
  test(
    'test an 500 response with error and detail body attributes with no ' +
      ' matching specificErrorMap entry results in the generic error message',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'noMatchingEntryInSpecificErrorMap',
              detail: 'detail',
            },
            status: 500,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage('name', {
          doesntMatch: new ResponseErrorMessage('title', 'message'),
        })
        expect(message.title).toBe('clientHandler.notCompletedTitle')
        expect(message.message).toBe('clientHandler.notCompletedDescription')
      }
    }
  )
  test('an 429 response results in a too many requests error', async () => {
    try {
      await errorInterceptorWithStubAppAndStore()({
        response: {
          status: 429,
        },
      })
    } catch (error) {
      const message = error.handler.getMessage('name')
      expect(message.title).toBe('clientHandler.tooManyRequestsTitle')
      expect(message.message).toBe('clientHandler.tooManyRequestsDescription')
    }
  })
  test('empty response results in a network error', async () => {
    try {
      await errorInterceptorWithStubAppAndStore()({})
    } catch (error) {
      const message = error.handler.getMessage('name')
      expect(message.title).toBe('clientHandler.networkErrorTitle')
      expect(message.message).toBe('clientHandler.networkErrorDescription')
    }
  })
  test(
    'test an 500 response that matches a default error returns its default ' +
      'message',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_USER_NOT_IN_GROUP',
              detail: 'detail',
            },
            status: 500,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage('name', {
          matchesSomeOtherError: new ResponseErrorMessage('title', 'message'),
        })
        expect(message.title).toBe('clientHandler.userNotInWorkspaceTitle')
        expect(message.message).toBe(
          'clientHandler.userNotInWorkspaceDescription'
        )
      }
    }
  )
  test(
    'test an 500 response that matches a default error returns its default ' +
      'message',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_USER_NOT_IN_GROUP',
              detail: 'detail',
            },
            status: 500,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage('name', {
          matchesSomeOtherError: new ResponseErrorMessage('title', 'message'),
        })
        expect(message.title).toBe('clientHandler.userNotInWorkspaceTitle')
        expect(message.message).toBe(
          'clientHandler.userNotInWorkspaceDescription'
        )
      }
    }
  )
  test('an 401 - ERROR_INVALID_REFRESH_TOKEN response redirect to the error page', async () => {
    const actualStoreDispatches = []
    const errorPageData = {}
    try {
      await errorInterceptorWithStubAppAndStore(
        actualStoreDispatches,
        errorPageData
      )({
        response: {
          data: { error: 'ERROR_INVALID_REFRESH_TOKEN' },
          status: 401,
        },
      })
    } catch (error) {
      expect(errorPageData.statusCode).toBe(401)
      expect(errorPageData.message).toBe('User session expired')
    }
  })
  test('an 404 response returns a not found error', async () => {
    try {
      await errorInterceptorWithStubAppAndStore()({
        response: {
          data: {},
          status: 404,
        },
      })
    } catch (error) {
      const message = error.handler.getMessage('name', {
        matchesSomeOtherError: new ResponseErrorMessage('title', 'message'),
      })
      expect(message.title).toBe('clientHandler.notFoundTitle')
      expect(message.message).toBe('clientHandler.notFoundDescription')
    }
  })
  test(
    'test an 400 response with a body validation error which doesnt match' +
      ' requestBodyErrorMap falls back to matching against specificErrorMap',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_REQUEST_BODY_VALIDATION',
              detail: { field: [{ code: 'no_matching_entry' }] },
            },
            status: 404,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage(
          'name',
          {
            ERROR_REQUEST_BODY_VALIDATION: new ResponseErrorMessage(
              'should fallback to this title',
              'should fallback to this message'
            ),
          },
          {
            field: {
              doesnt_match: new ResponseErrorMessage(
                "shouldn't match",
                "shouldn't match"
              ),
            },
          }
        )
        expect(message.title).toBe('should fallback to this title')
        expect(message.message).toBe('should fallback to this message')
      }
    }
  )
  test(
    'test an 400 response with a body validation error which does match' +
      ' requestBodyErrorMap doesnt falls back to matching against specificErrorMap',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_REQUEST_BODY_VALIDATION',
              detail: { field: [{ code: 'matchesRequestBodyErrorMap' }] },
            },
            status: 404,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage(
          'name',
          {
            ERROR_REQUEST_BODY_VALIDATION: new ResponseErrorMessage(
              "shouldn't match this fallback title",
              "shouldn't match this fallback message"
            ),
          },
          {
            field: {
              matchesRequestBodyErrorMap: new ResponseErrorMessage(
                'should match title',
                'should match description'
              ),
            },
          }
        )
        expect(message.title).toBe('should match title')
        expect(message.message).toBe('should match description')
      }
    }
  )
  test(
    'test an 400 response with a body validation error which doesnt match any map' +
      ' falls back to generic default',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_REQUEST_BODY_VALIDATION',
              detail: { field: [{ code: 'matchesRequestBodyErrorMap' }] },
            },
            status: 404,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage(
          'name',
          {
            SHOULD_NOT_MATCH: new ResponseErrorMessage(
              "shouldn't match this fallback title",
              "shouldn't match this fallback message"
            ),
          },
          {
            field: {
              shouldntMatch: new ResponseErrorMessage(
                'should not match title',
                'should not match description'
              ),
            },
          }
        )
        expect(message.title).toBe('clientHandler.notCompletedTitle')
        expect(message.message).toBe('clientHandler.notCompletedDescription')
      }
    }
  )
  test(
    'test an 400 response with a body validation error which has multiple errors ' +
      ' per field returns the first matched exception',
    async () => {
      try {
        await errorInterceptorWithStubAppAndStore()({
          response: {
            data: {
              error: 'ERROR_REQUEST_BODY_VALIDATION',
              detail: {
                other_field: [{ code: 'doesnt_match' }, { code: 'does_match' }],
                field: [{ code: 'doesnt_match' }, { code: 'does_match' }],
              },
            },
            status: 404,
          },
        })
      } catch (error) {
        const message = error.handler.getMessage(
          'name',
          {},
          {
            other_field: {
              no_matches: new ResponseErrorMessage(
                'should not match because for other field',
                'should not match because for other field'
              ),
            },
            field: {
              does_match: new ResponseErrorMessage(
                'should match title',
                'should match message'
              ),
            },
          }
        )
        expect(message.title).toBe('should match title')
        expect(message.message).toBe('should match message')
      }
    }
  )
  test('an 500 response returns action not completed error', async () => {
    try {
      await errorInterceptorWithStubAppAndStore()({
        response: 'traceback from backend',
      })
    } catch (error) {
      expect(error.response).toBe('traceback from backend')
      expect(error.handler.code).toBe(500)
      expect(error.handler.detail).toBe(null)
    }
  })
  describe('test invalid response details for request body validation errors', () => {
    const invalidDetails = [
      null,
      undefined,
      'string',
      1,
      [],
      1.0,
      false,
      BigInt(Number.MIN_SAFE_INTEGER),
      Symbol('test'),
      {},
      { weirdField: [] },
      { weirdField: null },
      { weirdField: undefined },
      { weirdField: 'string' },
      { weirdField: 1 },
      { weirdField: 1.0 },
      { weirdField: false },
      { weirdField: BigInt(Number.MIN_SAFE_INTEGER) },
      { weirdField: Symbol('weird key test') },
      { weirdField: [null] },
      { weirdField: [undefined] },
      { weirdField: ['string'] },
      { weirdField: [1] },
      { weirdField: [1.0] },
      { weirdField: [false] },
      { weirdField: [BigInt(Number.MIN_SAFE_INTEGER)] },
      { weirdField: [Symbol('weird inner detail value')] },
      { weirdField: [{}] },
      { weirdField: [{ code: [] }] },
      { weirdField: [{ code: null }] },
      { weirdField: [{ code: undefined }] },
      { weirdField: [{ code: 'string' }] },
      { weirdField: [{ code: 1 }] },
      { weirdField: [{ code: 1.0 }] },
      { weirdField: [{ code: {} }] },
      { weirdField: [{ code: false }] },
      { weirdField: [{ code: BigInt(Number.MAX_SAFE_INTEGER) }] },
      { weirdField: [{ code: Symbol('weird inner code value') }] },
    ]
    test.each(invalidDetails)(
      'with invalid detail %s',
      async (invalidDetail) => {
        try {
          await errorInterceptorWithStubAppAndStore()({
            response: {
              data: {
                error: 'ERROR_REQUEST_BODY_VALIDATION',
                detail: invalidDetail,
              },
              status: 400,
            },
          })
        } catch (error) {
          const message = error.handler.getMessage(
            'name',
            {
              matchesSomeOtherError: new ResponseErrorMessage(
                'title',
                'message'
              ),
            },
            {
              weirdField: {
                shouldNotMatchAnything: new ResponseErrorMessage(
                  'request body error matched title',
                  'request body error matched description'
                ),
              },
            }
          )
          expect(message.title).toBe('clientHandler.notCompletedTitle')
          expect(message.message).toBe('clientHandler.notCompletedDescription')
        }
      }
    )
  })
})
