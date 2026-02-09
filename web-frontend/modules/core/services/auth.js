export default (client) => {
  return {
    login(email, password) {
      return client.post('/user/token-auth/', { email, password })
    },
    blacklistToken(refreshToken) {
      return client.post('/user/token-blacklist/', {
        refresh_token: refreshToken,
      })
    },
    refresh(refreshToken) {
      return client.post(
        '/user/token-refresh/',
        { refresh_token: refreshToken },
        { skipAuthRefresh: true }
      )
    },
    register(
      email,
      name,
      password,
      language,
      authenticate = true,
      workspaceInvitationToken = null,
      templateId = null
    ) {
      const values = {
        name,
        email,
        password,
        authenticate,
        language,
      }

      if (workspaceInvitationToken !== null) {
        values.workspace_invitation_token = workspaceInvitationToken
      }

      if (templateId !== null) {
        values.template_id = templateId
      }

      return client.post('/user/', values)
    },
    sendResetPasswordEmail(email, baseUrl) {
      return client.post('/user/send-reset-password-email/', {
        email,
        base_url: baseUrl,
      })
    },
    resetPassword(token, password) {
      return client.post('/user/reset-password/', {
        token,
        password,
      })
    },
    changePassword(oldPassword, newPassword) {
      return client.post('/user/change-password/', {
        old_password: oldPassword,
        new_password: newPassword,
      })
    },
    sendChangeEmailConfirmation(newEmail, password, baseUrl) {
      return client.post('/user/send-change-email-confirmation/', {
        new_email: newEmail,
        password,
        base_url: baseUrl,
      })
    },
    changeEmail(token) {
      return client.post('/user/change-email/', {
        token,
      })
    },
    sendVerifyEmail(email) {
      return client.post(`/user/send-verify-email/`, {
        email,
      })
    },
    verifyEmail(token) {
      return client.post(`/user/verify-email/`, {
        token,
      })
    },
    dashboard() {
      return client.get('/user/dashboard/')
    },
    update(values) {
      return client.patch('/user/account/', values)
    },
    deleteAccount() {
      return client.post('/user/schedule-account-deletion/')
    },
    shareOnboardingDetailsWithBaserow(team, role, size, country) {
      return client.post('/user/share-onboarding-details-with-baserow/', {
        team,
        role,
        size,
        country,
      })
    },
  }
}
