import { describe, expect, test } from 'vitest'

import {
  canMakePrivate,
  canMakePublic,
  makePublicResubmits,
} from '@baserow/modules/core/utils/userTemplate'

describe('userTemplate visibility actions', () => {
  test.each([
    ['private', { can_make_public: true }, [true, false, false]],
    ['in_review', {}, [false, false, true]],
    ['rejected', { can_make_public: true }, [true, false, false]],
    [
      'rejected',
      { can_make_public: true, make_public_needs_review: true, listed: true },
      [true, true, true],
    ],
    ['public', { listed: true }, [false, false, true]],
    ['public', { can_make_public: true, listed: true }, [true, false, true]],
    ['blocked', {}, [false, false, false]],
  ])('offers the actions of a %s template %o', (state, fields, expected) => {
    const template = { state, ...fields }

    expect([
      canMakePublic(template),
      makePublicResubmits(template),
      canMakePrivate(template),
    ]).toStrictEqual(expected)
  })
})
