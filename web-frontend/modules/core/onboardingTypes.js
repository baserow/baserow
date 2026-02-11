import { Registerable } from '@baserow/modules/core/registry'

import UserPreview from '@baserow/modules/core/components/onboarding/UserPreview'
import MoreStep from '@baserow/modules/core/components/onboarding/MoreStep'
import AuthService from '@baserow/modules/core/services/auth'

export class OnboardingType extends Registerable {
  /**
   * The order in which the onboarding step must be. Note that if the complete
   * method depends on another step, then the order by be lower, otherwise not all
   * the data will be in there. Lowest one first.
   */
  getOrder() {
    throw new Error('getOrder is not implemented')
  }

  /**
   * The component that's displayed on the left side of the onboarding. This is
   * where the user must make a choice. It must contain a method called `isValid`.
   * If `true` is returned, then the user can click on the continue button. It can
   * $emit the `update-data` event to
   */
  getFormComponent() {
    throw new Error('getFormComponent is not implemented')
  }

  /**
   * The preview on the right side. Note that this isn't visible on smaller screens,
   * so it should just be for demo purposes. It can accept the data property
   * containing the data of all the steps.
   */
  getPreviewComponent(data) {
    return null
  }

  /**
   * Returns an object that is passed as props into the preview component.
   */
  getAdditionalPreviewProps() {
    return {}
  }

  /**
   * Called when the onboarding completes. This can be used to perform an action,
   * like a workspace that must be created, for example.
   * @param data contains the data that was collected by the form component.
   * @param responses the returned value of the `complete` method that was called by
   *  the already completed onboarding steps.
   * @param callback can be called if the message or loading component must be changed.
   *
   */
  complete(data, responses, callback) {}

  /**
   * Can optionally return a job that must be polled for completion. It will
   * automatically show a progress bar in that case. The job must be created in the
   * async complete function, this function should just respond with job object.
   * Note that the response of the completed job overwrites the response for this
   * step of the onboarding.
   */
  getJobForPolling(data, responses) {}

  /**
   * Can optionally return a route to where the user must be redirected after
   * completing all steps. Note that the last route will be used as we can only
   * redirect to one.
   */
  getCompletedRoute(data, responses) {}

  /**
   * Determine whether this step should be added based on a condition.
   * @param data contains the data that was collected by the form component.
   * @return boolean indicating whether this step must be executed.
   */
  condition(data) {
    return true
  }

  /**
   * Indicates whether if this step can manually be skipped by the user, by clicking
   * on "Skip for now". Note that if a step is skipped, no data will be added, so if
   * another step depends on the data, it must check whether it actually exists.
   */
  canSkip() {
    return false
  }
}

export class MoreOnboardingType extends OnboardingType {
  static getType() {
    return 'more'
  }

  getOrder() {
    return 10000
  }

  getFormComponent() {
    return MoreStep
  }

  getPreviewComponent() {
    return UserPreview
  }

  canSkip() {
    return true
  }

  async complete(data, responses) {
    const moreData = data[this.getType()]
    const share = moreData?.share

    if (share) {
      await AuthService(this.app.$client).shareOnboardingDetailsWithBaserow(
        moreData.team,
        'undefined',
        'undefined',
        moreData.country,
        moreData.how
      )
    }
  }
}
