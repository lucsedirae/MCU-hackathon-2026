# Streamlined workspace UX

Implemented on `dev`. Existing API permission and revision rules remain authoritative.

## Feature locations

| Feature | Location |
| --- | --- |
| Workspace switching and creation | Workspace sidebar |
| Ownership transfer | Workspace heading, administrator only |
| Accepted curriculum | Curriculum tab |
| Pending/rejected proposals and reopening | Proposals tab |
| Full preview, current-version comparison, acceptance/rejection | Proposal preview stages |
| Upload curriculum or report revisions | Revise / Upload report revision |
| AI review and generation, selected feedback | Review / Revise toolbar panels |
| Reports and report revisions | Reports tab and History |
| Runs, stop, source, results, immutable transcripts | Activity tab |
| Passage/general/table comments, replies, imported comments | Comments panel |
| Resolve, reopen, unresolved/resolved/unplaced filters | Comments panel |
| Carried comment original context | Each comment's original-context link |
| Versions, arbitrary comparisons, restoration | History |
| Previously generated exact exports | History |
| Word, Markdown, original downloads, unresolved comments option | Download |
| Import warnings | Import limitations notice |
| User creation/password reset | Administration → Team accounts |
| OpenAI key/model, testing, shared instructions | Administration → OpenAI settings |
| Password change/logout | User menu |

## Workflow rules preserved

- Owners alone change documents and run reviews; administrators do not gain owner privileges.
- All team members can read and comment. Authors/owners retain resolution rights.
- Curriculum acceptance still requires a fresh server comparison token against the current accepted version; it replaces the whole curriculum.
- Report uploads still become current immediately. Restoration retains its existing document-specific behavior.
- Original files, all revisions, comment provenance, exports, and transcripts remain available.
- No data migration is required.

## Validation

- Browser smoke: isolated database, upload, general/passage comments, compare, accept, download, persistence, mobile width.
- Secondary browser checks: comment filtering and resolution, passage navigation, restoration/rejection/reopening/acceptance, section navigation, review/revise panels, administration.
- Backend suite: 24 tests covering permissions, versioning, imports, exports, and provider settings.
- Frontend production build and desktop/mobile screenshot inspection.
