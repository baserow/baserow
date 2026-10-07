import { describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import {
  EmailInviteType,
  LinkInviteType,
} from '@baserow/modules/core/inviteTypes'

describe('Invite types', () => {
  test('registers the email invite type', async () => {
    const testApp = new TestApp()

    try {
      const inviteTypes = testApp.getRegistry().getOrderedList('invite')

      expect(inviteTypes).toHaveLength(1)
      expect(inviteTypes[0]).toBeInstanceOf(EmailInviteType)
    } finally {
      await testApp.afterEach()
    }
  })

  test('keeps the link invite type available for a feature-flagged rollout', () => {
    const linkInviteType = new LinkInviteType({
      app: { $i18n: { t: (key) => key } },
    })

    expect(linkInviteType.type).toBe('link')
    expect(linkInviteType.getName()).toBe('inviteType.link')
  })
})
