export default (client) => {
  return {
    create(
      workspaceId,
      shareURL,
      skipFiles,
      session,
      sessionSignature,
      applicationOptions = {}
    ) {
      return client.post(`/jobs/`, {
        ...applicationOptions,
        type: 'airtable',
        workspace_id: workspaceId,
        airtable_share_url: shareURL,
        skip_files: skipFiles,
        session,
        session_signature: sessionSignature,
      })
    },
  }
}
