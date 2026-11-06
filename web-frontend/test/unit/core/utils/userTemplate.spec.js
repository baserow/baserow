import { describe, expect, test } from 'vitest'

import {
  canMakePrivate,
  canMakePublic,
  makePublicResubmits,
} from '@baserow/modules/core/utils/userTemplate'

describe('userTemplate visibility actions', () => {
  // The owner's menu: [make public, which submits for review again, make private].
  test.each([
    ['private', { can_make_public: true }, [true, false, false]],
    ['in_review', {}, [false, false, true]],
    ['rejected', { can_make_public: true }, [true, false, true]],
    // Its approved version is listed, so only its change goes to review again.
    [
      'rejected',
      { can_make_public: true, make_public_needs_review: true, listed: true },
      [true, true, true],
    ],
    ['public', { listed: true }, [false, false, true]],
    // Its unsubmitted edit is listed at once, approval being off.
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
