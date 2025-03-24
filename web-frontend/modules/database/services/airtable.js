export default (client) => {
  return {
    create(workspaceId, shareURL, skipFiles, session, sessionSignature) {
      return client.post(`/jobs/`, {
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
