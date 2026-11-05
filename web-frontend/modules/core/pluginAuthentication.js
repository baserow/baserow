import { PasswordAuthProviderType } from '@baserow/modules/core/authProviderTypes'

/** Register sign-in providers without loading application feature registrations. */
export default async function register(nuxtApp) {
  nuxtApp.$registry.register(
    'authProvider',
    new PasswordAuthProviderType({ app: nuxtApp })
  )
}
