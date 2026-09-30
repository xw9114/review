# Knowledge detail and daily review UI contract

- `/knowledge/detail?point=ID` renders reviewed summary, notes, key points, questions and source
  provenance with the existing safe Markdown/LaTeX component. Do not render raw source HTML.
- Detail edits can add/remove up to five complete questions. Saving is blocked if a question or answer is empty.
- `/review` loads real statistics and resumes the active session. `?point=ID` offers targeted
  practice; `?session=ID` opens saved answers. Starting/revealing/rating are explicit clicks.
- Hide standard answers until reveal; preserve entered answers on errors and after reload once
  revealed. Show self-rating choices, next due date and the last ten completed session records.
- UI delegates scheduling to the backend, never computes mastery optimistically.
- Disable mutations while pending. Navigation/unload warns when edited text is not saved.
- Validate via isolated real-API browser workflow and 1440/390/320px light/dark screenshots.
- Dashboard queue failures do not turn a healthy knowledge library into an offline state.
