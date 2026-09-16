# Project workflow

- Develop on `dev`. Do not commit to or merge into `main`; the user handles merges.
- Before every commit and push to `dev`, review and update both:
  - `curriculum_review/frontend/src/UserTour.jsx` (the in-app user tour)
  - `curriculum_review/README.md` (setup and user documentation)
- Keep navigation labels, feature descriptions, role permissions, supported formats,
  and limitations consistent with the implementation. For changes that do not
  affect user instructions, explicitly record that the tour and README were
  reviewed in the README maintenance log and the tour's review metadata/comment.
  Do not invent a user-facing change just to alter documentation.
- Include documentation updates with the implementation commit. Before pushing
  existing commits, verify those updates are present and still accurate.
- Test changed tour steps, keyboard dismissal/navigation, administrator/member
  variants, and small-screen layout when the tour changes. Never use production
  accounts, data, or real provider calls for automated tests.
