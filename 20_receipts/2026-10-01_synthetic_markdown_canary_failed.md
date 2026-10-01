# C021 synthetic Markdown live proof: failed media method

Jeremy directly approved the prepared one-synthetic-Drive-file/one-source proof in
this delivery chat, then explicitly reiterated the scope. Earlier cross-chat
approval was rejected by platform review before execution; direct approval resolved
that blocker. This receipt reports observed failure, not successful qualification.

## Live scope and observations

- Google account: `jeremybradford1977@gmail.com`.
- Approved parent: `0AK0ss4S7aAQfUk9PVA`; same-account Drive v2 About returned
  precisely that `rootFolderId`. Ordinary folder metadata GET returned 404; root
  identity was established separately, without changing account/scope/credentials.
- One file created at 2026-10-01T22:36:26Z: `1ulyRxT8g14HF6FfSTmroSSECrKIn4X9u`,
  title `C021 individual Markdown conditional-write canary`, `text/markdown`,
  parent exactly as approved. Native transport preflight verified the file is
  editable, not trashed, owned by the expected account, and has exactly one owner
  permission before content upload was attempted.
- Initial synthetic upload failed. A bounded reproduction at
  2026-10-01T22:39:48Z recorded HTTP **404** for `PATCH` on the v2 media upload URI.
  Full readback remained empty with unchanged ETag. A diagnostic expected 405 and
  stopped after the actual 404; retain the actual response, not the expectation.
- File remains 0 bytes, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, ETag
  `"MTc5MDg5NDE4NjQ1MA"`. No successful PUT was attempted, no conditional-write
  enforcement was qualified, and no publication map/binding was created.
- Existing C010 notebook `c5b928c8-9913-4f6e-bbac-d1c3e00720b1` remains at
  114 sources, all selected as before. No new source ID exists; no restoration
  was needed because selections never changed. No Notebook query, manual Sync,
  Studio artifact, existing-material deletion or real-source publication occurred.
- Installed bundle provider/map/cohort/scheduler, OAuth configuration and security
  settings were not changed. A separate system-Python diagnostic was denied
  noninteractive Keychain access; the established venv interpreter succeeds. No
  credential or ACL repair was performed.

## Source finding and proposed continuation

Landed source PR #30 uses `PATCH` in
`src/notebooklm_mcp/doc_refresh/google_markdown_transport.py`. Google's primary
[Drive v2 update reference](https://developers.google.com/workspace/drive/api/reference/rest/v2/files/update)
documents `PUT` for the same media URI. The mismatch is reproduced live. Proposed
repair is a one-line method correction with an independently anchored service
contract regression, plus documentation/receipt/changelog updates. No module patch
or new review has been applied by this receipt.

Source landing remains merge `1b80bd31d8f938854b1bb3ddc68dbdbcd7641507`, identical
tree to reviewed head `26b6fa6d0cab96765394c9c1eef32b36826306e0`. Preserve all five
prior review attempts and original finding history. The postmerge audit/successor
route requires the operator instruction and review-7 extension if audit round 6
precedes repair round 7; neither new review has launched. After exact-head repair
clearance, reuse this same canary ID; never create a second file. Existing synthetic
live approval stands; source-repair/review scope is the next concrete decision.

Evidence files, retained in existing local review scratch:
`/Users/jeremybradford/LocalWork/Codex/c021-individual-review/`
`live-qualification-initial.json`, `live-preflight-diagnostic.json`,
`drive-root-observation.json`, `live-qualification.json`,
`canary-current-readback.json`, `live-existing-file-qualification.json`,
`live-source-repair-proposal.md`, `proposed-v2-method-repair.diff`.
[Owning issue observation](https://linear.app/macromancer/issue/WOR-853#comment-662ef3ec-7069-473c-b5ee-65c913861d3a).

Disposition: live proof incomplete. Retain the owner-only empty canary and original
sources. Source repair, independent review and same-ID proof remain open.
