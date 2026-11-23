import {
  FacebookAuthProviderType,
  GitHubAuthProviderType,
  GitLabAuthProviderType,
  GoogleAuthProviderType,
  OpenIdConnectAuthProviderType,
  PasswordAuthProviderType,
  SamlAuthProviderType,
} from '@baserow_enterprise/authProviderTypes'
/** Authentication providers shared by sign-in and application pages. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('authProvider', new PasswordAuthProviderType(context))
  $registry.register('authProvider', new SamlAuthProviderType(context))
  $registry.register('authProvider', new GoogleAuthProviderType(context))
  $registry.register('authProvider', new FacebookAuthProviderType(context))
  $registry.register('authProvider', new GitHubAuthProviderType(context))
  $registry.register('authProvider', new GitLabAuthProviderType(context))
  $registry.register('authProvider', new OpenIdConnectAuthProviderType(context))
}
