export function dashboardRunsUrl(workflowId: number | null | undefined, versionId?: number | null): string {
  const params = new URLSearchParams({ tab: 'runs' })
  if (Number.isFinite(workflowId) && Number(workflowId) > 0) {
    params.set('run_workflow_id', String(workflowId))
  }
  if (Number.isFinite(versionId) && Number(versionId) > 0) {
    params.set('run_version_id', String(versionId))
  }
  return `/ui?${params.toString()}`
}
