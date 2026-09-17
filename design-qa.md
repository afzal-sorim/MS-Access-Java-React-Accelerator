# Design QA — Operations Workspace generator theme

## Comparison target

- Source visual truth: the supplied MS Access-to-React screenshots, especially the dashboard, record-detail, and report views.
- Implementation screenshot: unavailable. This change adds a selectable generator theme; this workspace does not contain a persisted, runnable generated frontend for a browser capture.
- Viewport and density normalization: blocked pending generation and local browser capture at the source desktop viewport.
- State: not applicable until a converted application is generated with `ui_style: operations_workspace`.

## Findings

- [P1] Browser-rendered fidelity comparison is pending.
  Location: generated React output.
  Evidence: the theme and wizard build pass automated checks, but no browser screenshot of a generated Operations Workspace application is available alongside the supplied reference images.
  Impact: compact spacing, typography, record-rail density, and report layout cannot be certified as screenshot-level matches yet.
  Fix: generate a representative Access application with the new style, open its dashboard, data-bound form, and report views at the matching desktop viewport, then capture and compare them against the supplied screenshots.

## Required fidelity surfaces

- Fonts and typography: implemented with Inter and compact enterprise sizes; pending browser evidence.
- Spacing and layout rhythm: defined by the workspace grid, record rail, and detail sections; pending browser evidence.
- Colors and visual tokens: navy `#0b3b82`, white cards, and subdued operational status surfaces are defined; pending browser evidence.
- Image quality and asset fidelity: no custom image assets are required by this theme; supplied product logos are preserved by the generated application rather than recreated.
- Copy and content: titles, fields, actions, rows, and report metadata are generated dynamically from the Access IR.

## Implementation checklist

1. Generate a frontend using `operations_workspace`.
2. Capture dashboard, record-detail, report table, and report chart/state views.
3. Compare at the reference viewport and address any P0–P2 visual mismatches.

final result: blocked
