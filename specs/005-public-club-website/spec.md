# Feature Specification: Public Website for ALBERTOS Traditional Karate-Do Club

**Feature Branch**: `005-public-club-website`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Create a new feature: Public static website for ALBERTOS Traditional Karate-Do Club. The goal is to build a modern, responsive, visually polished and interactive public-facing website for the fictional ALBERTOS Traditional Karate-Do club. This feature is separate from the existing RAG chatbot functionality. Do not modify the chatbot/RAG behavior unless integration is explicitly required by a later feature. The website content may be fictional... [full 15-point requirements list covering: public unauthenticated access; home page with hero/CTAs/news/sections/trainer/benefits/contact; a Traditional Karate-Do educational page; a fictional club history page; a trainers page; a club sections/locations page; an interactive training schedule filterable by location/day/age-level; a news ('Aktualności') section; a contact page with optional non-functional form; restrained interactivity (mobile nav, filtering, reveal animations); a premium non-stereotypical martial-arts visual identity; architectural separation from the RAG/domain application with no new backend systems (CMS, accounts, payments, booking, DB tables) unless later specified; no regression to the existing FastAPI/RAG/Ollama application; automated test coverage for page availability, navigation, schedule/news filtering, and existing-suite non-regression; and a minimum page set: Strona główna, O karate tradycyjnym, O klubie / Historia, Trenerzy, Sekcje, Grafik, Aktualności, Kontakt]."

## Clarifications

No `[NEEDS CLARIFICATION]` markers were needed. The source request is itself
detailed and prescriptive enough that every open question below has a single
reasonable default consistent with the existing Albercik/ALBERTOS product
(Polish-language, single-tenant, security-conscious FastAPI app) — see
Assumptions.

### Session 2026-08-19

- Q: The original spec (FR-007) explicitly avoided a Japanese-themed visual
  identity in favor of a generic "clean, premium, modern sports-club"
  aesthetic. The product owner asked to reverse this: the site should be in
  a Japanese style. → A: FR-007 amended — the visual identity now
  deliberately embraces an authentic, restrained Japanese design language
  (natural materials, negative space, a disciplined traditional palette,
  calligraphy-inspired type accents, sparing traditional motifs), while
  still explicitly avoiding tacky/kitsch execution (no neon, no cluttered
  novelty symbols, no generic dashboard/card layouts) — see the amended
  FR-007 below.
- Q: The spec used "Traditional Karate" throughout when describing the
  discipline itself. The product owner clarified the site should describe
  the discipline as "Traditional Karate-Do" (the "-Do"/"way" framing), not
  plain "Traditional Karate", and asked for a terminology/glossary section
  explaining common Japanese dojo terms (e.g., Mokuso, Seiza, Gyaku Tsuki).
  → A: All discipline-descriptive references updated to "Traditional
  Karate-Do" throughout the spec. At the time, the club's own proper name,
  "ALBERTOS Traditional Karate-Do Club", was deliberately left unchanged as an
  established brand name distinct from discipline terminology — **this was
  superseded the same day, see below.** A new terminology/glossary
  requirement (FR-018a/FR-018b) and Key Entity ("Glossary Term") were added
  to the Traditional Karate-Do page (User Story 5) — see those sections
  below.
- Q: A follow-up pass found the feature title still read "Traditional
  Karate", and the product owner asked for "Traditional Karate-Do"
  everywhere, superseding the prior decision to leave the club's proper
  name unchanged. → A: The feature title is now "Public Website for
  ALBERTOS Traditional Karate-Do Club". The historical **Input** field
  (the verbatim original feature request) was subsequently edited to
  match as well, so it too now reads "Traditional Karate-Do" throughout
  — the "→ A:" prose earlier in this Clarifications log still correctly
  describes what the spec used to say before each amendment and is left
  as-is for that reason.
- Q: What should the news page show when a category filter matches no
  posts? → A: Mirror the schedule's existing empty-state pattern (FR-025)
  — a clear "no news in this category" message with an easy way to clear
  the filter. See FR-029a, User Story 7's new Acceptance Scenario 5, and
  the corresponding Edge Cases entry below.
- Q: What page-load time should count as "fast" (the original request's
  "Fast loading" goal had no measurable target)? → A: Under 2 seconds for
  a primary page to become usable, under typical broadband/mobile network
  conditions — see FR-002a and SC-010.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-time visitor gets oriented and knows how to join (Priority: P1)

A prospective member (or a parent of a prospective young member) finds the
ALBERTOS website, lands on the home page, and within seconds understands what
the club is, what Traditional Karate-Do training looks like, and what to do
next — either start training or find out more.

**Why this priority**: This is the front door of the whole feature. Without a
credible, orienting home page with a clear call to action, nothing else on
the site matters — this alone is a deployable, demonstrable MVP.

**Independent Test**: Load the home page with no authentication and no other
page implemented; confirm the hero section, a short Traditional Karate-Do
introduction, a primary "join" call to action, a secondary call to action
toward the schedule, and a contact call to action are all present and
readable on a single visit.

**Acceptance Scenarios**:

1. **Given** a visitor with no prior knowledge of ALBERTOS, **When** they open
   the home page, **Then** they see a hero section identifying the club and
   Traditional Karate-Do, a short introductory description, and a primary call
   to action inviting them to join or attend a first training.
2. **Given** the home page is loaded, **When** the visitor scrolls down,
   **Then** they encounter, in some reasonable order, a secondary call to
   action toward the training schedule, a preview of the latest news, a
   preview of the club's training locations, a short trainer introduction,
   a summary of training benefits, and a contact call to action.
3. **Given** the visitor is on a mobile-sized viewport, **When** they view
   the home page, **Then** all of the above content remains readable and
   usable without horizontal scrolling or overlapping elements.

---

### User Story 2 - Visitor finds a training session that fits their schedule (Priority: P2)

A visitor who has decided they're interested wants to know exactly when and
where they can attend a session appropriate for their age or skill level.

**Why this priority**: Converting interest into an actual visit to a training
session is the single most valuable action this website can drive, and it
depends on functionality (filtering), not just static content — the natural
second slice after the home page.

**Independent Test**: Navigate directly to the training schedule page and,
without any other content page implemented, filter sessions by location, by
day, and by age/skill level, and confirm the visible list of sessions updates
accordingly.

**Acceptance Scenarios**:

1. **Given** the training schedule page is loaded, **When** no filter is
   applied, **Then** all published training sessions are visible, each
   showing its location, day, time, and age/skill group.
2. **Given** the visitor selects a specific location, **When** the filter is
   applied, **Then** only sessions at that location remain visible.
3. **Given** the visitor selects a day and an age/skill group in addition to
   a location, **When** all three filters are applied together, **Then**
   only sessions matching all three criteria remain visible.
4. **Given** a filter combination matches no sessions, **When** it is
   applied, **Then** the visitor sees a clear message that no sessions match,
   rather than an empty or broken-looking page.
5. **Given** the visitor is on a mobile-sized viewport, **When** they use the
   schedule filters, **Then** the filter controls and results remain fully
   usable without requiring desktop-only interactions (e.g., hover-only
   controls).

---

### User Story 3 - Visitor learns which location/section fits them (Priority: P3)

A visitor wants to see the club's training locations as concrete places with
their own groups, trainers, and schedule, so they can decide where to attend.

**Why this priority**: Underpins the schedule (User Story 2) with the
descriptive detail (address, assigned trainer, age/skill groups) that a bare
schedule table doesn't convey, and stands alone as a useful page for someone
who prefers to browse by place rather than by time.

**Independent Test**: Navigate directly to the sections/locations page and
confirm each location displays its name, address, training groups, age/skill
levels, training days and hours, and assigned trainer, without depending on
the schedule or trainers page being implemented.

**Acceptance Scenarios**:

1. **Given** the sections/locations page is loaded, **When** the visitor
   views it, **Then** every training location is listed with its name,
   address, the groups trained there, their age/skill level, their days and
   hours, and the trainer assigned to them.
2. **Given** a location listing, **When** the visitor selects a trainer name
   shown there, **Then** they can reach that trainer's profile (User Story
   4).

---

### User Story 4 - Visitor learns about the trainers (Priority: P4)

A visitor, especially a parent, wants to know who is actually teaching the
classes — their experience, grade, and specialization — before committing.

**Why this priority**: Builds the credibility and trust needed to convert an
interested visitor into an attendee; independently valuable as a stand-alone
"meet the team" page.

**Independent Test**: Navigate directly to the trainers page and confirm each
trainer profile shows a name, role, karate grade, specialization, short
biography, and the section(s)/location(s) they teach, with a photo
placeholder, independent of any other page.

**Acceptance Scenarios**:

1. **Given** the trainers page is loaded, **When** the visitor views it,
   **Then** each trainer is presented with a name, role, grade,
   specialization, short biography, and the section(s) they teach.
2. **Given** a trainer has no photo available, **When** their profile is
   displayed, **Then** a visually consistent placeholder is shown instead of
   a broken image or empty gap.

---

### User Story 5 - Visitor understands what Traditional Karate-Do is (Priority: P5)

A visitor unfamiliar with Traditional Karate-Do wants a plain, credible
explanation of the discipline before deciding whether it's for them or their
child.

**Why this priority**: Educational trust-building content that supports the
join decision but doesn't block it — useful as a standalone reference page
independent of scheduling or club-specific detail.

**Independent Test**: Navigate directly to the Traditional Karate-Do page and
confirm it explains what Traditional Karate-Do is, its philosophy/values, its
three core practice areas (kihon, kata, kumite), dojo etiquette, belt
progression, benefits by age group, and a glossary of common Japanese dojo
terms, without depending on any other page.

**Acceptance Scenarios**:

1. **Given** the Traditional Karate-Do page is loaded, **When** the visitor
   reads it, **Then** they find general, non-club-specific educational
   content covering what Traditional Karate-Do is, its philosophy and values,
   kihon/kata/kumite, dojo etiquette, belt progression, and benefits for
   children, teenagers, and adults.
2. **Given** the page discusses real-world organizations, historical
   figures, or specific dates, **When** the visitor reads it, **Then** no
   such claim is presented unless it is already verified content elsewhere
   in this project — generic, non-attributed educational framing is used
   instead.
3. **Given** the Traditional Karate-Do page includes a terminology/glossary
   section, **When** the visitor browses it, **Then** they find common dojo
   commands and technique names (for example: Mokuso, Seiza, Rei, Kiai,
   Gyaku Tsuki, Kihon, Kata, Kumite) each paired with a short, plain-language
   explanation of what it means and, where relevant, when it's used.
4. **Given** the visitor is looking for one specific term, **When** they use
   the glossary, **Then** they can find it without reading the entire page
   top to bottom (e.g., via grouping, search, or alphabetical/categorical
   organization).

---

### User Story 6 - Visitor reads the club's story (Priority: P6)

A visitor wants a sense of the club's identity and community — where it came
from and how it has grown — to feel it's an established, credible place to
train.

**Why this priority**: Reinforces credibility and belonging; a self-contained
narrative page that doesn't depend on any other content being present.

**Independent Test**: Navigate directly to the club history page and confirm
it presents a coherent fictional narrative covering the club's origins, its
first training groups, the growth of new sections, camps/examinations, and
the current community, clearly framed as website content rather than
verified fact.

**Acceptance Scenarios**:

1. **Given** the club history page is loaded, **When** the visitor reads it,
   **Then** they see a narrative covering the club's origins, its first
   groups, the growth of additional sections, camps and examinations, and
   the current community.
2. **Given** the history page is fictional, **When** the visitor reads any
   part of it, **Then** nothing on the page or elsewhere on the site implies
   it is verified, real-world historical fact about an actual organization.

---

### User Story 7 - Visitor catches up on club news (Priority: P7)

A visitor, especially an existing or returning member, wants to see what's
currently happening at the club — new seasons, camps, exams, events.

**Why this priority**: Signals an active, currently-operating club, which
supports the join decision; independently useful and independently testable
without any other page.

**Independent Test**: Navigate directly to the news ("Aktualności") page and
confirm several example news posts are listed with title, date, category, and
summary, that selecting one shows its full content, and that filtering by
category narrows the visible list.

**Acceptance Scenarios**:

1. **Given** the news page is loaded, **When** the visitor views it,
   **Then** they see a list of news posts, each showing at least a title,
   date, category, and short summary, and, when provided, an image.
2. **Given** the visitor selects a news post, **When** it opens, **Then**
   they see its full article content.
3. **Given** the visitor filters the news list by category, **When** the
   filter is applied, **Then** only posts in that category remain visible.
4. **Given** the home page's "latest news" preview (User Story 1), **When**
   the visitor selects "see all news" or an individual preview item,
   **Then** they land on this news page (or the specific post).
5. **Given** a category filter matches no posts, **When** it is applied,
   **Then** the visitor sees a clear "no news in this category" message,
   with an easy way to clear the filter, rather than an empty or
   broken-looking page.

---

### User Story 8 - Visitor gets in touch with the club (Priority: P8)

A visitor who has decided to join, or who has a question, wants a clear,
findable way to reach the club.

**Why this priority**: The final conversion step referenced by CTAs
throughout the site; kept last because it is the smallest, most
self-contained page, but every other story links to it.

**Independent Test**: Navigate directly to the contact page and confirm it
shows phone, email, a list of training locations, social-media placeholders,
and (if included) a contact form whose non-functional/static nature is
verifiable by inspection and by an automated test that submitting it performs
no network call and causes no error.

**Acceptance Scenarios**:

1. **Given** the contact page is loaded, **When** the visitor views it,
   **Then** they see a phone number, an email address, the club's training
   locations, and social-media placeholders.
2. **Given** a contact form is present, **When** the visitor fills it out and
   submits it, **Then** no real message is sent anywhere (no backend/email
   integration exists), and the visitor is not misled into believing one was
   sent to a monitored inbox unless a real integration is explicitly
   implemented.

---

### Edge Cases

- What happens when a schedule filter combination matches zero sessions? A
  clear "no sessions match your filters" message is shown, with an easy way
  to clear the filters (User Story 2, Acceptance Scenario 4).
- What happens when a news category filter matches zero posts? A clear "no
  news in this category" message is shown, with an easy way to clear the
  filter (User Story 7, Acceptance Scenario 5) — the same pattern as the
  schedule's empty state, for consistency.
- What happens when a trainer or news post has no photo/image? A consistent
  visual placeholder is shown instead of a broken image reference.
- What happens when JavaScript is unavailable? Static content (all page
  text, the unfiltered schedule, the unfiltered news list) remains readable;
  only the interactive filtering/animation enhancements degrade gracefully.
- What happens on very small (≤360px) or very large (≥1920px) viewports?
  Layout remains usable and readable without horizontal scrolling or
  unreadably stretched content.
- What happens when a visitor navigates directly to a specific news post or
  location via a bookmarked/shared link? The specific item's content loads
  correctly without requiring the visitor to first pass through a listing
  page.
- What happens when the existing chatbot/API routes are exercised while the
  new website pages are also deployed? Both must work independently; neither
  interferes with the other's behavior, data, or configuration.
- What happens if a visitor attempts to reach an authenticated/admin-only
  area from the public site? The public website exposes no path into the
  existing admin/authentication surface beyond what already exists.

## Requirements *(mandatory)*

### Functional Requirements

**Global / cross-cutting**

- **FR-001**: The public website MUST be reachable without authentication of
  any kind.
- **FR-002**: The public website MUST render correctly and remain fully
  usable at common mobile, tablet, and desktop viewport widths.
- **FR-002a**: **Added 2026-08-19** (see Clarifications). A primary page
  MUST become usable (visible, readable content, ready for interaction) in
  under 2 seconds under typical broadband/mobile network conditions,
  consistent with the site's static/public-content nature.
- **FR-003**: The public website MUST provide accessible, semantic
  navigation reaching every primary page (Strona główna, O Karate-Do
  (Karate Tradycyjne), O klubie / Historia, Trenerzy, Sekcje, Grafik, Aktualności,
  Kontakt) from any page, including a usable mobile navigation pattern.
- **FR-004**: The public website MUST use semantic HTML structure (headings,
  landmarks, lists, alt text on meaningful images) sufficient for
  screen-reader and keyboard navigation of primary content and navigation.
- **FR-005**: The public website's content (page copy, trainer bios, club
  history, news posts) MUST be presented in Polish, consistent with the
  existing ALBERTOS product's language.
- **FR-006**: The public website MUST clearly be presented as content for
  the fictional ALBERTOS club; any historically- or organizationally-framed
  content (Traditional Karate-Do background, club history) MUST NOT be
  presented as verified real-world fact about a real organization, person,
  or date unless that fact is already verified content elsewhere in this
  project.
- **FR-007**: **Amended 2026-08-19** (see Clarifications). The public
  website's visual design MUST embrace an authentic, elevated Japanese
  design language — restrained natural materials and negative space
  ("ma"), a disciplined palette (e.g., deep indigo/black/off-white with a
  single accent such as red), calligraphy-inspired typography accents, and
  subtle traditional motifs (e.g., an engawa/dojo-floor sense of line and
  space, an enso circle used sparingly) — combined with modern web-club
  polish. It MUST still avoid tacky/kitsch execution: no neon effects, no
  cluttered novelty symbol usage, and no generic dashboard/card-heavy
  layouts; the goal is a credible, premium *dojo* feeling, not a tourist- 
  shop pastiche.
- **FR-008**: Interactive enhancements (menu open/close, filtering, reveal
  animations, hover/transition effects) MUST be restrained enough not to
  impede readability, and MUST NOT block access to underlying content if
  they fail to run.

**Home page**

- **FR-009**: The home page MUST include a hero section identifying the club
  and Traditional Karate-Do.
- **FR-010**: The home page MUST include a short introduction to Traditional
  Karate-Do.
- **FR-011**: The home page MUST include a primary call to action inviting
  the visitor to join or attend a first training (e.g., "Dołącz do nas" /
  "Przyjdź na pierwszy trening").
- **FR-012**: The home page MUST include a secondary call to action leading
  to the training schedule.
- **FR-013**: The home page MUST show a preview of the most recent news
  posts, linking to the full news page/post.
- **FR-014**: The home page MUST show a preview of the club's training
  locations/sections.
- **FR-015**: The home page MUST include a short trainer presentation.
- **FR-016**: The home page MUST present the benefits of training at
  ALBERTOS / reasons to choose the club.
- **FR-017**: The home page MUST include a call to action leading to the
  contact page/section.

**Traditional Karate-Do page**

- **FR-018**: The Traditional Karate-Do page MUST explain, in general
  (non-club-specific) educational terms: what Traditional Karate-Do is, its
  philosophy and values, its three core practice areas (kihon, kata,
  kumite), dojo etiquette and culture, belt progression, and its benefits
  for children, teenagers, and adults.
- **FR-018a**: **Added 2026-08-19** (see Clarifications). The Traditional
  Karate-Do page MUST include a terminology/glossary section explaining
  common Japanese dojo terms in plain language — at minimum commands and
  concepts used during a typical class (e.g., Mokuso, Seiza, Rei, Kiai) and
  basic technique names (e.g., Gyaku Tsuki, and representative kihon/kata/
  kumite vocabulary) — each with its term, a plain-language explanation of
  what it means, and, where relevant, when/how it's used during training.
- **FR-018b**: The glossary MUST be organized so a visitor can locate a
  specific term without reading the full page top to bottom (e.g., grouped
  by category such as commands/etiquette vs. technique names, and/or
  alphabetically ordered).

**Club history page**

- **FR-019**: The club history page MUST present a fictional narrative
  covering the club's origins, its first training groups, the growth of new
  sections, camps and examinations, and the current community, and MUST be
  identifiable as website/demo content rather than verified history.

**Trainers page**

- **FR-020**: The trainers page MUST list fictional trainer profiles, each
  with a name, role, karate grade, specialization, short biography, and the
  section(s)/location(s) they teach.
- **FR-021**: Each trainer profile MUST support a photo, with a consistent
  visual placeholder when no photo is available.

**Sections / locations page**

- **FR-022**: The sections/locations page MUST list each training
  location's name, address, training groups, age/skill level, training days
  and hours, and assigned trainer.

**Training schedule**

- **FR-023**: The training schedule MUST list every published training
  session with its location, day, time, and age/skill group.
- **FR-024**: The training schedule MUST let visitors filter sessions by
  location, by day, and by age/skill group, individually and in
  combination.
- **FR-025**: The training schedule MUST show a clear empty-state message
  when a filter combination matches no sessions.
- **FR-026**: The training schedule MUST NOT require or offer any booking,
  reservation, or account-creation capability — it is display/filter only.

**News page**

- **FR-027**: The news page MUST list fictional example news posts covering
  at least: a new training season, a karate camp, a belt examination, a
  tournament/event, and a new beginners group.
- **FR-028**: Each news post MUST support a title, date, category, short
  summary, optional image, and full article content.
- **FR-029**: The news page MUST let visitors filter posts by category.
- **FR-029a**: **Added 2026-08-19** (see Clarifications). The news page
  MUST show a clear empty-state message — mirroring FR-025's schedule
  empty-state pattern — when a category filter matches no posts, with an
  easy way to clear the filter.
- **FR-030**: Selecting a news post MUST show its full article content.
- **FR-031**: News content MUST be sourced from static, structured
  project data/files — no content-management or admin interface is part of
  this feature.

**Contact page**

- **FR-032**: The contact page MUST show a phone number, an email address,
  the club's training locations, and social-media placeholders.
- **FR-033**: The contact page MAY include a visual contact form; if
  included, it MUST be clearly non-functional/static (no backend email
  delivery or persistence), and this MUST be verifiable by automated test
  (submitting it triggers no network request and no error).

**Architecture / non-regression**

- **FR-034**: The public website's content and presentation logic MUST be
  kept separate from the existing RAG/domain/application logic (retrieval,
  embeddings, LLM providers, answerability logic, Ollama configuration).
- **FR-035**: The public website's structured content (trainers, locations,
  schedule, news) MUST be sourced from static project data rather than a
  database, unless a later specification explicitly requires persistence.
- **FR-036**: This feature MUST NOT introduce a CMS, user accounts,
  payments, a training-registration backend, a booking system, or new
  database tables.
- **FR-037**: This feature MUST NOT modify the existing chatbot/RAG
  behavior, retrieval, embeddings, LLM providers, answerability logic,
  Ollama configuration, the eval benchmark, or existing API contracts,
  except where strictly necessary to serve the new public website (e.g.,
  adding new, additive routes) — and any such change MUST leave all
  existing automated tests passing.
- **FR-038**: The existing FastAPI/RAG/Ollama application MUST continue to
  function exactly as before this feature is added.

### Key Entities *(include if feature involves data)*

- **Training Location / Section**: A place where the club trains — name,
  address, the training groups held there, their age/skill level(s),
  training days and hours, and the trainer(s) assigned to it. Referenced by
  the schedule, the sections page, the home page preview, and trainer
  profiles.
- **Training Session**: A single scheduled recurring class — the location it
  belongs to, day(s) and time, and the age/skill group it serves. The unit
  the schedule page filters over.
- **Trainer**: A person teaching at the club — name, role, karate grade,
  specialization, short biography, photo (or placeholder), and the
  section(s)/location(s) they teach. Referenced by the trainers page,
  sections/locations, and the home page preview.
- **News Post**: A published club update — title, date, category, short
  summary, optional image, and full article content. Referenced by the news
  page and the home page's latest-news preview.
- **Glossary Term**: **Added 2026-08-19.** A dojo term explained on the
  Traditional Karate-Do page — the term itself (e.g., "Mokuso", "Seiza",
  "Gyaku Tsuki"), a category (e.g., command/etiquette vs. technique name),
  and a plain-language explanation of its meaning and, where relevant, when
  it's used. Referenced only by the Traditional Karate-Do page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time visitor can identify, without scrolling, at least
  one clear way to join or attend a first training within the first few
  seconds of loading the home page.
- **SC-002**: A visitor can narrow the training schedule down to sessions
  matching a specific location, day, and age/skill group using 3 or fewer
  interactions.
- **SC-003**: All 8 primary pages (Strona główna, O Karate-Do (Karate
  Tradycyjne), O klubie / Historia, Trenerzy, Sekcje, Grafik, Aktualności, Kontakt) load
  and remain fully readable and usable at mobile, tablet, and desktop
  viewport widths, with no horizontal scrolling or overlapping content.
- **SC-004**: Every primary page is reachable from the home page's
  navigation within 2 clicks/taps.
- **SC-005**: A visitor can locate and read at least 5 distinct fictional
  news posts, each covering a different example topic (season, camp, exam,
  event, new group), and can narrow that list by category.
- **SC-006**: A visitor can locate at least 3 fictional trainer profiles and
  at least 2 distinct training locations, each with the complete attribute
  set specified for that entity.
- **SC-007**: 100% of the automated test suite that existed before this
  feature continues to pass after it is added, with zero behavioral changes
  to existing chatbot/API functionality.
- **SC-008**: With interactive JavaScript-driven enhancements disabled, all
  static page content (text, unfiltered schedule, unfiltered news list)
  remains readable and reachable.
- **SC-009**: **Added 2026-08-19.** A visitor can locate at least 8 distinct
  dojo terms in the Traditional Karate-Do page's glossary, each with a
  plain-language explanation, and can find a specific term without reading
  the entire page top to bottom.
- **SC-010**: **Added 2026-08-19.** Each primary page becomes usable
  (visible, readable content, ready for interaction) in under 2 seconds
  under typical broadband/mobile network conditions.

## Assumptions

- **Delivery mechanism**: the public website is delivered as new,
  additive, unauthenticated presentation surface within the existing
  Albercik application deployment (no new deployable service, container, or
  database is introduced), consistent with FR-037/FR-038's "strictly
  necessary to serve the public website" allowance. The concrete technical
  approach is a planning-phase decision, not a specification-phase one.
- **Content language**: all visitor-facing website copy is in Polish,
  matching the existing ALBERTOS/Albercik product's language, per the
  Polish page names and CTA text already given in the feature request.
- **Content authenticity**: all club-specific content (trainers, history,
  news, sections/locations, schedule) is clearly fictional demo content for
  this project; only the general Traditional Karate-Do educational content
  avoids unsupported real-world claims, per FR-006.
- **Imagery**: trainer photos, news images, and any other photography are
  out of scope to source or license for this feature; visually consistent
  placeholders stand in for real photography.
- **Contact form**: if included, the contact page's form is presented
  visually but is non-functional (no backend email/persistence integration)
  for this feature, per FR-033.
- **No real-time/session data**: the schedule, news, trainers, and locations
  are static structured content maintained as part of the project, not
  editable by any public or administrative UI introduced by this feature.
- **Existing security posture unaffected**: because the public website adds
  no authentication, no user input persistence, and no new data-bearing
  endpoints beyond static content and non-functional form UI, it does not
  expand the existing application's security-sensitive surface area (rate
  limiting, budget, kill switch, JWT auth) — those existing controls are
  unaffected and out of scope for this feature to modify.
