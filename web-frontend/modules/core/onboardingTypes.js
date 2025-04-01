import { Registerable } from '@baserow/modules/core/registry'

import UserPreview from '@baserow/modules/core/components/onboarding/UserPreview'
import InviteStep from '@baserow/modules/core/components/onboarding/InviteStep'
import MoreStep from '@baserow/modules/core/components/onboarding/MoreStep'
import TeamStep from '@baserow/modules/core/components/onboarding/TeamStep'
import WorkspaceStep from '@baserow/modules/core/components/onboarding/WorkspaceStep'
import AppLayoutPreview from '@baserow/modules/core/components/onboarding/AppLayoutPreview'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import AuthService from '@baserow/modules/core/services/auth'
import { MemberRoleType } from '@baserow/modules/database/roleTypes'

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
   *
   */
  complete(data, responses) {}

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

export class TeamOnboardingType extends OnboardingType {
  static getType() {
    return 'team'
  }

  getOrder() {
    return 1100
  }

  getFormComponent() {
    return TeamStep
  }

  getPreviewComponent() {
    return UserPreview
  }

  canSkip() {
    return true
  }
}

export class MoreOnboardingType extends OnboardingType {
  static getType() {
    return 'more'
  }

  getOrder() {
    return 1200
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
    const teamData = data[TeamOnboardingType.getType()]
    const moreData = data[this.getType()]
    const share = moreData?.share

    if (share) {
      const team = teamData?.team || 'undefined'
      await AuthService(this.app.$client).shareOnboardingDetailsWithBaserow(
        team,
        moreData.role,
        moreData.companySize,
        moreData.country
      )
    }
  }
}

export class WorkspaceOnboardingType extends OnboardingType {
  static getType() {
    return 'workspace'
  }

  getOrder() {
    return 1300
  }

  getFormComponent() {
    return WorkspaceStep
  }

  getPreviewComponent() {
    return AppLayoutPreview
  }

  async complete(data, responses) {
    return await this.app.store.dispatch('workspace/create', {
      name: data[this.getType()].name,
    })
  }

  canSkip() {
    return false
  }
}

export class InviteOnboardingType extends OnboardingType {
  static getType() {
    return 'invite'
  }

  getOrder() {
    return 1400
  }

  getFormComponent() {
    return InviteStep
  }

  getPreviewComponent() {
    return AppLayoutPreview
  }

  getAdditionalPreviewProps() {
    return { highlightDataName: 'members' }
  }

  async complete(data, responses) {
    if (!Object.prototype.hasOwnProperty.call(data, this.getType())) {
      return
    }

    const emails = data[this.getType()].emails
    const acceptUrl = `${this.app.$config.BASEROW_EMBEDDED_SHARE_URL}/workspace-invitation`
    for (let i = 0; i < emails.length; i++) {
      const values = {
        email: emails[i],
        permissions: MemberRoleType.getType(),
      }
      await WorkspaceService(this.app.$client).sendInvitation(
        responses[WorkspaceOnboardingType.getType()].id,
        acceptUrl,
        values
      )
    }
  }

  canSkip() {
    return true
  }
}
