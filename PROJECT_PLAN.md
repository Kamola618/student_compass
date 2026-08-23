# Student Compass — Project Plan

Draft v1 · 23 Aug 2026 · based on a walkthrough of `newuzbekistan.hero.study` (HeRo "Study Space") and the current Django code in this repo.

---

## 1. What the university platform actually is

I explored the live platform logged in as your account. It is an Angular SPA on a REST API at `api.newuzbekistan.hero.study/v1/`, with **21 modules**:

| Module | Route | What it holds |
|---|---|---|
| Dashboard | `/dashboard` | 9 tiles, pure navigation |
| My subjects | `/subjects`, `/subjects/{id}` | 25 disciplines across 5 semesters; per-course description, code, credits, ECTS, lecture/lab split, teachers, materials |
| Academic plan | `/educational-plan` | **The richest page.** Full curriculum: index code, LEC/TUT/LAB hours, credits, prerequisites, post-requisites, status per course, credits per semester, 178 total |
| Gradebook | `/gradebook` | Per-semester grades (currently empty — registration not complete) |
| Transcript | `/transcript` | Official record; program 60610400 Software Engineering, Bachelor, CS dept |
| Assignment | `/homework` | "Independent works" with a 7-state status machine |
| Testing and controls | `/testing-controls` | Intermediate control / Final control |
| Time Schedule | `/calendar` | Day + week grid, 09:00–23:00 in 55-min slots; lesson registration; cohorts |
| Notes and tasks | `/notes-and-tasks` | Personal notes + tasks (empty for you) |
| IGPA | `/igpa` | Achievement records by semester |
| Others | `/news` `/library` `/reference` `/finance` `/polls` `/student-requests` `/vacancies-catalog` `/advisor` `/academic-calendar` `/profile` | Administrative + content |

**Two structures worth stealing outright:**

*Homework status machine* — Not ready → In process → On completion → Under review → Ready, plus Not submitted and Archive. That is a genuinely well-modelled lifecycle and much better than your current boolean-ish `progress` integer.

*Curriculum graph* — courses carry prerequisites and post-requisites. This makes the academic plan a DAG, not a list. That is the single most interesting data structure on the whole platform and nothing in the UI does anything clever with it.

**Weaknesses I noticed** (worth beating, not copying):
- Localisation leaks badly. On one English page I saw `СТАТУС`, `Не готово`, `КУРС`, `СР`, and `Today 23 Авгус` — Russian strings bleeding through the English locale.
- Raw HTML renders as literal text in course descriptions: `<p><span style="color:rgb(0,0,0);...">` shows up on screen.
- Everything is backward-looking. It records what happened. Nothing anywhere answers *"what do I need to do next?"*
- Dashboard tiles animate constantly and carry no data — nine big images that are pure navigation.

---

## 2. Strategic framing — the most important decision

**Do not clone all 21 modules.** Most of that platform is a *system of record* owned by the registrar: enrollment, official grades, transcripts, finance, requests. You cannot reproduce those — you have no authority to issue a transcript, and no data source for other students.

What you *can* own is the half the university platform ignores. Your existing `Course.target_status_for()` already computes **"what score do I need on remaining work to hit my target grade?"** The university platform has nothing like it. That is your product.

So the framing I recommend:

> **Student Compass is a planning layer, not a records layer.** The university tells you what you got. Compass tells you what to do next.

That reframing decides everything downstream: you build the grade engine, the workload planner, and the curriculum graph — and you *skip* finance, requests, library, news, polls, and vacancies entirely.

I'd hold off on scraping the HeRo API to auto-import your real data. It's technically feasible from what I saw, but it's their system, the terms are unknown, and building on an undocumented private API means your app breaks whenever they redeploy. Manual entry (or CSV import) for v1; revisit later if you want.

---

## 3. Current codebase — what to keep, fix, and delete

Your repo has `Semester`, `Course`, `Assignment`, `Grade`, `Assessment`, `StudentGrade`, 142 lines of views, 6 templates.

**Keep:** the grade engine concept. `target_status_for()` with its `reached` / `needed` / `unreachable` states is genuinely good thinking and is the core of the product.

**Fix — four real problems:**

1. **Two competing grading systems.** `Grade` (fixed midterm/assignments/final weights) and `Assessment` + `StudentGrade` (flexible, any number of weighted components) both exist and both implement `current_total`, `letter_grade`, `gpa_point`, `target_status`. Migration `0003` added the second without removing the first. `Grade` is the weaker design — delete it and migrate its data into `Assessment` rows.

2. **`Course` and `Assignment` have no owner.** Neither has a FK to `User`. Only `StudentGrade` does. So the app is single-user in practice while pretending otherwise — any logged-in user sees every user's courses. This must be fixed before any deploy.

3. **`score_for()` ignores the user it is passed.** In the `auto_calculated` branch it runs `self.assignment_set.aggregate(Avg('score'))` — averaging every assignment on the course regardless of who owns it. Once `Assignment` gets a user FK this needs filtering, otherwise your average silently blends in other people's scores.

4. **`venv/` and `db.sqlite3` are committed to git.** The venv is machine-specific and will conflict constantly; the sqlite file will conflict on every run. Both need `git rm --cached`. (I added a `.gitignore`, but that doesn't untrack files already in the index.)

---

## 4. Proposed data model

```
User
 └── StudentProfile      program, cohort/group, enrollment year, target GPA

Semester                 name, start/end, is_active
 └── Enrollment          user × Course × Semester  ← ownership lives here
      └── Assessment     name, weight, kind(intermediate|final|coursework), auto_calculated
           └── Score     obtained value, max value, graded_at

Course                   code (SE201), title, credits, ects, lec/tut/lab hours, description
 ├── prerequisites       M2M → Course   ← the curriculum DAG
 └── post-requisites     reverse of the above

Task                     title, course?, due_at, status(7-state), priority, difficulty,
                         estimated_minutes, actual_minutes
Note                     title, body, course?, pinned
```

Two deliberate changes from what you have now:

**`Enrollment` as the join table.** Ownership moves off `Course` entirely. A `Course` becomes a shared catalogue entry (SE201 Web Programming, 6 credits, prereqs) while `Enrollment` is *your* instance of it in a given semester. This fixes problem #2 cleanly and makes the curriculum graph shareable between users.

**Scores as obtained/max rather than percent.** You currently store `score` as a float assumed to be a percentage. Storing `17.5 / 20` instead of `87.5` means you can show real marks, and it makes partial-credit and ungraded states unambiguous.

---

## 5. Milestones

**M1 — Foundation** *(fix what's broken before adding anything)*
Untrack venv and db.sqlite3. Custom user + `StudentProfile`. Introduce `Enrollment`, migrate `Course`/`Assignment` ownership onto it. Delete the `Grade` model, migrating its data to `Assessment`. Fix `score_for()` user filtering. Real auth pages. First tests — the grade engine deserves them.

**M2 — Grade engine** *(the core product)*
Flexible weighted assessments per enrollment. Current total, letter, GPA. Target calculator: "you need 78% on the final for an A." Semester GPA and cumulative GPA. Make the NewUU scale (A+ 93/4.5 … F 0) configurable rather than a hardcoded list on two models.

**M3 — Workload planner**
Adopt the 7-state task lifecycle. Calendar and list views. Priority × difficulty × due-date ordering. The "what should I do today?" view — this is the thing the university platform has no answer for.

**M4 — Curriculum graph**
Import the academic plan structure. Visualise prerequisites as a DAG. Credit progress toward 178. "What unlocks if I pass CS 111?" — note your plan shows CS 111 Algorithms and Data Structures as PASSED UNSUCCESSFULLY, which is exactly the case where a prerequisite graph earns its keep by showing what's blocked downstream.

**M5 — Polish**
Dashboard that leads with *decisions*, not navigation tiles. Proper i18n done right — EN/RU/UZ with no leakage, since that's an obvious win over theirs. Responsive layout. Deploy.

I'd treat M1+M2 as the real first release. M3 makes it daily-use. M4 is the differentiator but only pays off once M1's data model is right.

---

## 6. Tech decisions

Stay on Django with server-rendered templates. Adding a SPA frontend would triple the work for no benefit here. If you want interactivity in M3's calendar, **HTMX + Alpine.js** gets you there without a build step or a second codebase.

Move off SQLite to Postgres at M5 when you deploy, not before. Add `pytest-django` at M1 — the grade engine is pure logic with tricky edge cases (zero remaining weight, all-ungraded courses, unreachable targets) and is exactly what tests are for. Split settings into base/dev/prod; `SECRET_KEY` and `DEBUG` need to leave source control before deploy.

Rename the `main` app to something meaningful (`academics`?) while the project is still small enough that it's cheap.

---

## 7. Decisions made

**Multi-user — confirmed.** Groupmates are users, not just you. Two consequences:

*M1 grows.* Proper auth, per-user data isolation, and the `Enrollment` split stop being nice-to-have and become the foundation. Problem #2 in section 3 is now a blocker, not a cleanup.

*But it also solves the biggest risk.* The thing that kills apps like this is **data-entry friction** — nobody wants to type in twelve courses and forty assessment weights before seeing any value. Multi-user fixes it: `Course` is a shared catalogue, so when one JSE2 student enters SE201's structure, everyone in the group inherits it. First user pays the cost, everyone after gets a one-click import. That reframes the shared catalogue from "nice architecture" to **the onboarding strategy**, and it's a strong argument for doing the `Enrollment` split properly in M1 rather than retrofitting.

**Milestone order — validated, keep M2 → M3 → M4.** The standard sequencing is activation → retention → differentiation, and the current order maps onto it:

- **M2 (grade engine) is the activation moment.** "You need 78% on the final for an A" is the first time the app tells you something you didn't already know. That's the hook.
- **M3 (planner) is the retention loop.** Grades get checked a few times a semester; tasks get checked daily. Retention is the first signal that matters — if people use it once and never come back, you have a demo, not a product.
- **M4 (curriculum graph) is the differentiator, and differentiators come last** — after the core value is proven. Users don't use most features; they use two or three obsessively. Build M4 once you know which two.

The trap to avoid is building M4 first because it's the most fun. It's the most impressive *and* the least load-bearing.

## 8. Still open

1. **Manual entry, CSV import, or API sync** for getting real course data in? (Shared catalogue softens this a lot.)
2. **Coursework with a deadline, or a portfolio project?** Changes polish-versus-breadth.
3. **Scope check:** does dropping finance/library/news/polls/requests entirely sit right?
4. **Visual direction** — see section 9.

---

## 9. Visual direction

**Warm & editorial** — confirmed, and it was already latent in the original templates: paper `#FBF3E7`, burgundy `#6B1E3C`, Fraunces / Inter / IBM Plex Mono. Those tokens were copy-pasted into five templates, which is how palettes drift. They now live once, in `static/css/compass.css`.

Two things were missing and have been added, because they are what separates "considered" from "competent":

**A spacing scale.** `--s1` through `--s8`, 4px base. Nothing in a template should use an off-scale pixel value. Inconsistent spacing is the loudest amateur tell — louder than colour or font choice.

**A type scale.** Five sizes for the entire app. Hierarchy comes from weight, colour, and family — Fraunces for display, Inter for interface, Plex Mono for anything numeric so figures align in columns.

Working rules, enforced by the token set:

- One accent. Burgundy marks primary actions and active nav, nothing else. Semantic colours (`--ok`, `--warn`, `--risk`) are desaturated to sit inside a warm palette rather than fighting it.
- Borders *or* shadows on a surface, never both. Cards use a hairline border.
- Never `#000` on `#FFF` — `--ink` is `#2E1620`, warm, on warm paper.
- Empty states are designed screens, not blank space. Every list view has one with an illustration mark, a sentence, and a single action, because a new user's first screen is always the empty one.
- Demo data uses real NewUU course names, never lorem ipsum — placeholder text hides the layout problems that long titles cause.

## 10. M1 status

Done: environment repaired (the venv held only pip — Django was running from system Python); `db.sqlite3` untracked; the empty `user` app removed; `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` moved to env; models rebuilt around `Enrollment`; the duplicate `Grade` model deleted; the user-leak bug fixed and covered by a regression test; grade engine extracted to `main/grading.py` as pure functions; 24 tests passing; design system extracted; all templates rebuilt on a shared base.

**One design correction found by running it.** `total()` counts only *banked* points, so mid-semester every course reads as an F — a 91 on the midterm with the final still pending showed as F, and semester GPA showed 1.35. Arithmetically right, useless to look at. Display now uses `projected_total()` / `projected_letter()`, with the banked figure kept for the target calculator where it is the correct input. Same data, opposite conclusion, and only visible by looking at the rendered page.

Not done, deliberately: the `main` app is still called `main` (rename when convenient), no CSV import yet, no shared-catalogue import flow yet — that belongs with M2.
