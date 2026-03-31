import { Registerable } from '@baserow/modules/core/registry'
import CloudflareTurnstileWidget from '@baserow/modules/core/components/auth/CloudflareTurnstileWidget'

/**
 * A captcha provider type defines how a specific captcha service is rendered
 * and interacted with on the frontend. Each provider must return a Vue component
 * via getComponent() that handles rendering the captcha widget.
 *
 * The component must:
 * - Accept a `captchaSettings` prop (Object) containing the full captcha settings
 *   from the backend (e.g. site_key, provider, enabled_contexts). Each provider
 *   component extracts the fields it needs from this object.
 * - Emit a `token` event with the captcha response token (or empty string on
 *   expiry/error)
 * - Expose a `reset()` method via defineExpose or $refs
 */
export class CaptchaProviderType extends Registerable {
  /**
   * Returns the Vue component that renders this captcha provider's widget.
   */
  getComponent() {
    throw new Error('The component of a captcha provider type must be set.')
  }

  constructor(...args) {
    super(...args)

    if (this.type === null) {
      throw new Error('The type of a captcha provider type must be set.')
    }
  }
}

export class CloudflareTurnstileCaptchaProviderType extends CaptchaProviderType {
  static getType() {
    return 'cloudflare_turnstile'
  }

  getComponent() {
    return CloudflareTurnstileWidget
  }
}
