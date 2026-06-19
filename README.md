# 🏛️ The Clent Consort | Full-Stack Web Application

[![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/StockoL/clent-consort-project-ms1?color=success)](https://github.com/StockoL/clent-consort-project-ms1)
[![Lighthouse Performance](https://img.shields.io/badge/Lighthouse_Performance-98%25-brightgreen)](#testing)
[![Lighthouse Accessibility](https://img.shields.io/badge/Lighthouse_Accessibility-100%25-brightgreen)](#testing)

**[🔴 LIVE APPLICATION: Click here to view the deployed application on Render (Staging)](#)** _(Placeholder for live link)_

The Clent Consort is a bespoke, full-stack web application developed for an amateur choral ensemble based in the Clent Hills, Worcestershire.

Moving beyond a simple static brochure, the application is engineered as a dual-purpose digital ecosystem. It provides a high-visibility "Electronic Press Kit" (EPK) to secure prestigious ecclesiastical residencies, while simultaneously serving as a secure, database-driven logistics hub for the active members of the choir. Built on a Python/Django backend with a bespoke, utility-first CSS architecture, the development prioritises clean, DRY (Don't Repeat Yourself) code principles and high-performance accessibility.

---

## <a name="top"></a>📋 Table of Contents

1. [📖 Project Purpose & User Stories](#purpose)
2. [🔬 Strategic Research & UX Design (The 5 Planes)](#ux-strategy)
3. [🖼️ Phase 1: Frontend Architecture & CSS Primitives](#frontend-architecture)
4. [⚙️ Phase 2: Backend Production (Django Integration)](#backend-architecture)
5. [✨ Core Features & Page Implementations](#features)
6. [🏗️ Development Log & Engineering Phases](#dev-log)
7. [🧪 Testing & Quality Assurance Portfolio](#testing)
8. [🌐 Deployment Guide](#deployment)
9. [🤖 Architectural Collaboration with AI](#ai-collab)

---

## 1. <a name="purpose"></a> 📖 Project Purpose & User Stories

The objective is to architect a high-performance web application that serves as both a public-facing promotional tool and a functional resource hub. The core user requirements have been mapped using Behavior-Driven Development (BDD) acceptance criteria to ensure technical implementations directly serve user goals.

### 1. The Ecclesiastical Stakeholder (Cathedral Deans)

_Focus: Professionalism, musical excellence, and reliability._

- **User Story:** As a Cathedral Dean, I want to review the ensemble's digital portfolio and track record so that I can verify they are a "safe pair of hands" to cover a weekend residency.
  - **BDD Acceptance Criterion:** **Given** a Cathedral Dean is evaluating ensembles for a weekend residency, **When** they navigate to the 'About' and 'Events' pages, **Then** they are presented with a professional digital EPK and a track record demonstrating musical excellence.

### 2. The Patron & Prospective Member

_Focus: Access, repertoire, and logistics._

- **User Story:** As a local resident, I want access to a performance calendar so I can purchase tickets to upcoming local events.
  - **BDD Acceptance Criterion:** **Given** a local resident is seeking live choral music, **When** they visit the 'Events' page, **Then** they see a chronological calendar of upcoming performances with clear geographical and booking details.
- **User Story:** As a prospective singer, I want to see the current repertoire to assess the musical alignment and commitment level of the choir before auditioning.
  - **BDD Acceptance Criterion:** **Given** a prospective singer is considering joining the ensemble, **When** they review the public repertoire and event history, **Then** they can accurately assess the ensemble's musical alignment before submitting an audition request via the dual-stream Contact form.

### 3. The Active Chorister

_Focus: Utility, sheet music access, and scheduling._

- **User Story:** As a current member, I want a centralised resource area to retrieve sheet music PDFs, practice tracks, and rehearsal schedules efficiently on a mobile device.
  - **BDD Acceptance Criterion:** **Given** an active chorister requires logistics for an upcoming rehearsal, **When** they log securely into the Member Dashboard on a mobile device, **Then** they can access their specific voice part's schedule and execute "Clickable Row" document retrieval with zero layout overflow.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 2. <a name="ux-strategy"></a> 🔬 Strategic Research & UX Design (The 5 Planes)

### Strategic Research

To ensure the site meets real-world needs, a product audit of local ensemble websites was conducted. Findings showed that most provided concert dates and an engaging EPK experience. However, practically none boasted an effective "members' area" for resource sharing, opting instead for fragmented email chains. The Clent Consort application bridges this gap by unifying public promotion and internal logistics.

### I. Strategy & Scope

- **Phase 1 (Frontend MVP):** Build a responsive, highly accessible static site using semantic HTML and a bespoke CSS architecture.
- **Phase 2 (Backend Production):** Transition the static prototype into a dynamic web application using Python/Django, introducing secure user authentication, a PostgreSQL database, and cloud AWS media storage.

### II. Structure & Skeleton

- **The Patron's Path:** Home > Events > Venue Map/Details > Contact.
- **The Stakeholder's Path:** Home > About (Credentials) > Events (Track Record) > Contact (Booking).
- **Resilient UX (404 Strategy):** A custom 404 page is implemented with a prominent "Return to Home" button to prevent navigational dead-ends.

### III. Surface (Typography & Aesthetics)

The visual surface enforces a **"Cathedral Aesthetic"**—utilising deep charcoal (`#1a1a1a`), stone neutrals, and gold accents (`#c9a45e`).

- **Display Typography (Cinzel):** Selected for classical Roman proportions evoking the timeless nature of choral music. Uppercase styling and increased tracking evoke luxury and historical weight.
- **Body Typography (Inter):** A high-performance sans-serif with an exceptional x-height for digital clarity. Ensures that logistical data (dates/times/venues) remains instantly digestible on mobile screens.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 3. <a name="frontend-architecture"></a> 🖼️ Phase 1: Frontend Architecture & CSS Primitives

My approach to the frontend UI avoids bloated frameworks like Bootstrap. Instead, it relies on a bespoke, utility-first CSS architecture heavily influenced by the **Every Layout** methodology (Heydon Pickering & Andy Bell).

### Axiomatic Layout Primitives

Instead of relying on rigid, breakpoint-heavy media queries, the site uses intrinsic layouts that leverage the browser's native engine computing constraints algorithmically.

- **The Stack (`.l-stack > * + *`):** Utilises the "Lobotomised Owl" (adjacent sibling selector) to inject vertical rhythm strictly _between_ elements. This provides a single source of truth for spacing, mathematically tied to a CSS Custom Property scale (`--s-1` to `--s5`).
- **The Switcher (`.l-switcher`):** A container-based logic gate (`flex-basis: calc((var(--threshold) - 100%) * 999);`). If the container is narrower than the defined threshold (e.g., 40rem), the calculation evaluates to a massive integer, forcing elements to grow and wrap automatically.
- **The Sidebar (`.l-sidebar`):** Uses a high flex-grow hack (`flex-grow: 999`) on the content column, allowing complex asymmetrical layouts (like the Conductor's bio) to manage themselves fluidly.
- **The Reel (`.l-reel`):** Provides a smooth, horizontal scrolling experience using native CSS Flexbox and Scroll Snapping (`scroll-snap-type: x mandatory`), bypassing heavy JavaScript carousels that damage performance scores.
- **The Unified Invert (`.box.invert`):** A modular card primitive enforcing the dark-mode aesthetic. This DRY approach means any layout can become a high-contrast container simply by stacking these two classes.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 4. <a name="backend-architecture"></a> ⚙️ Phase 2: Backend Production (Django Integration)

To elevate the project from a static portfolio to a functional, live application, the architecture was migrated to **Python** and the **Django 5.0** framework.

### Django Architecture & Template Inheritance

The static Phase 1 HTML files were completely deconstructed into a modular Django template system.

- **The Master Skeleton (`base.html`):** The global `<head>`, persistent sticky navigation, and footer grid were extracted into a single master template.
- **DRY Rendering:** Individual pages (e.g., `events.html`) were refactored to use `{% extends 'choir/base.html' %}` and `{% block content %}`. This ensures that any adjustments to the main navigation automatically cascade across the entire application simultaneously.

### The Authentication Perimeter (Django-Allauth)

The "Member Resource Area" required a secure gateway. I implemented the `django-allauth` package to manage cryptographic hashing and user sessions.

- **Invite-Only Protocol:** Because this is a private ensemble, public registration poses a security risk. I integrated `django-invitations`, configuring `INVITATIONS_INVITE_ONLY = True`. Member accounts can now only be provisioned via secure, single-use cryptographic email tokens dispatched by the director.
- **Bespoke UI Overrides:** Default Allauth templates visually break bespoke frontend design systems. I engineered a complete override by mapping Allauth's backend hooks (e.g., mapping the expected `login` field to my `type="email"` input) directly into custom HTML files located in `templates/account/`. This ensured the entire password-reset and login journey remained visually identical to the established `.box .invert` CSS primitives.

### Cloud Storage (AWS S3 & WhiteNoise)

A choral ensemble generates massive files (PDF scores, MP3 rehearsal tracks). Storing these directly on the web server would cause severe database bloat and performance degradation.

- **Amazon Web Services (S3):** I configured the `boto3` and `django-storages` packages to offload all user-uploaded media to an AWS S3 bucket. When a director uploads a new score via the Django Admin panel, it is automatically routed to AWS, keeping the core server lean.
- **Static File Delivery:** Django's `runserver` does not serve static assets (CSS/JS) in production environments. I implemented `WhiteNoise` middleware to intercept static file requests, apply Brotli/Gzip compression, and serve them securely and efficiently directly from the WSGI server.

### Python Configuration & Security

The `settings.py` file was completely refactored to safely handle the transition from a local laptop to the live internet.

- **Environment Isolation (`.env`):** Integrated `python-dotenv`. All sensitive routing and cryptographic keys (AWS keys, `SECRET_KEY`, database credentials) are extracted into an isolated `.env` file, ensuring they are never committed to version control.
- **Database Abstraction:** Utilised `dj-database-url`. If `DEBUG=True`, Django connects to a local `db.sqlite3` file. In production, the environment variable dynamically maps Django's ORM to a high-performance **PostgreSQL** database.
- **Security Hardening:** Implemented strict environmental logic. When `DEBUG=False` (production), Django automatically enforces `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and restricts incoming traffic via a defined `ALLOWED_HOSTS` array.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 5. <a name="features"></a> ✨ Core Features & Page Implementations

- **index.html:** Features a high-performance Hero Section utilizing fluid typography (`clamp()`) and `<link rel="preload">` to ensure near-instant Largest Contentful Paint (LCP). A semi-transparent CSS gradient overlay guarantees WCAG 2.1 contrast ratios regardless of the background image's original brightness.
- **about.html (Scrollytelling):** Employs pure CSS "Scrollytelling" using the experimental `view-timeline` API. As users swipe horizontally through the "Project Rhythm," background videos provide atmospheric context while text performs scroll-driven reveal animations.
- **contact.html (Dual-Stream Forms):** Utilises the `.l-switcher` primitive (`--threshold: 60rem`). Booking and Audition forms sit side-by-side on wide screens but stack on mobile. Forms are styled with high-contrast "White Well" inputs to exceed accessibility requirements, complete with `:focus-visible` gold box-shadows.
- **members.html (Algorithmic Dashboard):** Engineered a high-density dashboard. Employs progressive disclosure `<details>` accordions to prevent YouTube iframes from tanking initial page loads. The Voice Part Hubs utilise a "Clickable Row" pattern designed around Fitts's Law, providing a massive 48px touch target for musicians attempting to download PDFs while at a music stand.
- **Administrative Control Center (Django Admin):** Leveraged Django's built-in Admin panel, heavily customized for the ensemble director. Provides a secure GUI to perform CRUD operations on chorister profiles, event dates, and seamlessly upload PDF scores directly to AWS S3 without needing to touch a line of code.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 6. <a name="dev-log"></a> 🏗️ Development Log & Engineering Phases

To ensure a clean, maintainable, and scalable codebase, this application was built iteratively.

### Phase 1: Frontend Technical Log

- **Logo Aspect Ratio Distortion:** Identified that flexbox expansions were horizontally stretching the logo on the member dashboard. _Fix:_ Refactored the raw asset to a perfect 1:1 canvas size in GIMP and enforced strict `width/height` HTML attributes.
- **Mobile Viewport Overflow:** During iPhone SE testing, the layout broke horizontally, creating a "nested pressure cooker" effect that disabled vertical scrolling. _Fix:_ Refactored the global `<body>` to `min-height: 100vh` (instead of fixed `100vh`) and applied `max-width: 100%` safety valves to all intrinsic child primitives (`.l-switcher`, `.l-sidebar`), restoring fluid scrolling constraints.
- **The Sticky Footer Anchoring:** On sparse pages (like 404), the footer floated awkwardly in the middle of the screen. _Fix:_ Engineered a flexbox global layout, applying `flex: 1` to the `<main>` element to act as a "greedy" container, automatically pushing the footer flush to the bottom viewport edge.

### Phase 2: Backend Technical Log

- **ModuleNotFoundError during Deployment Checks:** Python crashed when trying to parse the production `settings.py` due to missing cloud libraries. _Fix:_ Synchronised the virtual environment using `pip install gunicorn whitenoise psycopg2-binary dj-database-url`, and locked the manifest via `pip freeze > requirements.txt`.
- **Allauth Security Feedback Loop:** The default Allauth login form lacked interactive user feedback. _Fix:_ Engineered a state-driven CSS border system using `:placeholder-shown`, `:valid`, and `:invalid` pseudo-classes. The input remains neutral until typing begins, turning red for structural errors, and locking to a green success state natively before the form is even submitted.
- **Dynamic Email Routing:** A hardcoded `EMAIL_BACKEND` broke the application flow. If pushed to production, emails would only print to the server log. _Fix:_ Refactored `settings.py` to check the `DEBUG` state. Locally, it prints to the terminal; in production, it fetches secure `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` App Passwords from the `.env` variables to dispatch real SMTP invitations.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 7. <a name="testing"></a> 🧪 Testing & Quality Assurance Portfolio

### Lighthouse Performance Audits

Performance optimisation was targeted directly through structural CSS changes and pre-loading critical path assets.

| Page    | Performance | Accessibility | Best Practices | SEO |
| :------ | :---------- | :------------ | :------------- | :-- |
| Index   | 98          | 100           | 100            | 100 |
| About   | 89          | 95            | 77\*           | 100 |
| Events  | 99          | 95            | 100            | 100 |
| Contact | 99          | 96            | 100            | 100 |
| Members | 100         | 95            | 100            | 100 |

_\* Best Practices scores on the About and Members pages reflect the intentional inclusion of Spotify and YouTube iframes. I chose to prioritise the User Experience (providing choral context via audio) over a synthetic 100 score, mitigating impact via `loading="lazy"`._

### W3C Validation

- **HTML:** All markup validated against HTML5 standards. Flagged `<time>` elements were resolved by implementing the `datetime` attribute (ISO 8601 standard) for SEO/Accessibility.
- **CSS Jigsaw:** Parse errors regarding `view-timeline` and `animation-timeline` are documented as intentional architectural decisions belonging to the emerging CSS Animation Level 4 specification. They provide high-end progressive enhancement (scrollytelling) while gracefully degrading in legacy browsers.

### Manual Verification Matrix

- **Security Perimeter Check:** Attempted to force-navigate to `/members/` directly via the URL bar while logged out. _Result:_ Django `AccountMiddleware` successfully intercepted the request and executed an HTTP 302 redirect to the `/accounts/login/` protocol.
- **Asset Delivery Check:** Clicked "Download Logistics Pack" from the member dashboard. _Result:_ `boto3` successfully routed the request to the correct AWS S3 bucket region, serving the PDF in a new `_blank` tab.

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 8. <a name="deployment"></a> 🌐 Deployment Guide

This project is built with Git version control and is configured for automated cloud deployment via **Render**.

### Production Build Script (`build.sh`)

To automate server compilation, the following shell script executes on Render upon every push to the `main` branch:

```bash
#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install all production dependencies
pip install -r requirements.txt

# 2. Tell WhiteNoise to collect and compress all CSS/JS files
python manage.py collectstatic --no-input

# 3. Build the PostgreSQL database tables
python manage.py migrate
```

### Local Deployment (Cloning for Development/Auditing)

To run this full-stack application locally on your own machine:

1. Open your terminal and clone the repository:
   git clone https://github.com/StockoL/clent-consort-project-ms1.git

2. Navigate into the directory and create a virtual environment:
   `python -m venv .venv`

3. Activate the environment:

- Windows: `.venv\Scripts\activate`

- Mac/Linux: `source .venv/bin/activate`

4. Install the project dependencies:
   `pip install -r requirements.txt`

5. Create a `.env` file in the root directory and add a placeholder security key and debug flag:

```py
SECRET_KEY=local_development_key_123
DEBUG=True
```

6. Run migrations to build the local SQLite database:
   `python manage.py migrate`

7. Start the development server:
   `python manage.py runserver`

8. Navigate to `http://127.0.0.1:8000/` in your browser

## <p align="right">(<a href="#top">Back to top</a>)</p>

## 9. <a name="ai-collab"></a> 🤖 Architectural Collaboration with AI

Artificial Intelligence (LLMs) was utilised strictly as a "Pair Programmer" throughout the development lifecycle to accelerate reflow profiling, troubleshoot complex backend logic, and ensure absolute human ownership of the overarching engine code.

- **System Axioms:** I established the "Golden Rules" — specifically the Spacing Scale, Typography Hierarchy, CSS Compositional Primitives, and Python DRY code principles.
- **Prompt Engineering:** Used Gemini to troubleshoot complex CSS parsing errors in Phase 1, and to securely translate static HTML templates into the Django inheritance structure during Phase 2.
- **Refinement:** I manually audited all AI outputs to ensure they respected requirements such as my primitive systems, stripping out redundant media queries or forced absolute positioning suggested by the AI. The resulting codebase is a hybrid of human-led architectural vision and AI-assisted execution.

## <p align="right">(<a href="#top">Back to top</a>)</p>
