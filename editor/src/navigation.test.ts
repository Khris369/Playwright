import { describe, expect, it } from 'vitest'
import { dashboardRunsUrl } from './navigation'

describe('dashboardRunsUrl', () => {
  it('defaults to the runs tab and includes the workflow and version', () => {
    expect(dashboardRunsUrl(42, 7)).toBe('/ui?tab=runs&run_workflow_id=42&return_to_editor=%2Fui%2Feditor%3Fworkflow_id%3D42&run_version_id=7')
  })

  it('omits absent ids', () => {
    expect(dashboardRunsUrl(undefined, undefined)).toBe('/ui?tab=runs')
    expect(dashboardRunsUrl(42, null)).toBe('/ui?tab=runs&run_workflow_id=42&return_to_editor=%2Fui%2Feditor%3Fworkflow_id%3D42')
  })
})
