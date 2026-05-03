# Technical Presentation Video Script

## Purpose

This script is for a more formal technical presentation. It explains the architecture, implementation details, teamwork, version control, testing, and practical value of the prototype.

Suggested length: 5 to 8 minutes.

---

## 1. Project Overview

Our project is a student schedule management and course knowledge workspace system.

The main goal is solving a common student problem: managing class schedules, checking today’s courses, and quickly finding what class you’re in right now.

The second part connects each course with a knowledge workspace where students can upload PDF or DOCX notes, organize them by topic, search through everything, ask questions, and view a knowledge graph.

We built it with FastAPI on the backend and Vue 2 on the frontend. We went with browser pages instead of a command-line interface so we could test it in a realistic user flow.

---

## 2. Backend Architecture

The backend is organized into clear layers.

The `routers` layer handles HTTP endpoints. It's intentionally thin—mostly just validates requests, checks login state, and calls services.

The `services` layer contains business logic: authentication, schedule management, note processing, knowledge retrieval, and graph construction.

The `storage` layer handles persistence. Schedule data goes into JSON files, while note metadata and chunks go into SQLite. Uploaded files are saved on disk.

The `models` layer uses Pydantic to define request and response structures, which keeps the API consistent and makes the Swagger docs easier to understand.

This separation makes maintenance easier. The frontend doesn't need to know how schedules are stored—it just calls stable API endpoints.

A typical request looks like this: the browser sends a request like `GET /query/overview`, the router reads the `session_token` cookie and asks the auth service for the current student ID, the service layer loads the required data from storage, and the response comes back as a Pydantic model with a stable JSON structure.

We use this pattern throughout the system, which gives us a consistent way to add new features without mixing page logic, business logic, and persistence logic in the same file.

---

## 3. Authentication and Session Design

The system uses local account registration and login.

After login, the backend creates a session token and stores it in a cookie named `session_token`. Later requests use this cookie to identify the current user.

This design fits a browser-based prototype well and keeps the frontend simple because same-origin requests include the cookie automatically.

Protected pages like `/dashboard` and `/knowledge-workspace` are guarded by the backend. If you're not logged in, the server redirects you to `/login`.

The implementation centers around `AuthService`. During registration, the user gets stored by student ID. During login, the service verifies the password, creates a random token, and records the session in memory.

For each protected request, the service checks whether the cookie exists, whether the token exists in the session table, and whether the session is still valid. If any check fails, the router returns `401` for APIs or redirects for page routes.

It's simple enough for a course project, but still close to real web behavior: the browser uses a cookie, protected resources are guarded by the backend, and the frontend doesn't store passwords or session state manually.

---

## 4. Schedule Module

The schedule module supports semester initialization, manual course entry, schedule upload, course editing, deletion, and weekly timetable queries.

Each course includes a course name, teacher, location, weekday, period range, active weeks, and week type.

The semester start date is used to calculate the current teaching week. Based on that week number, the system can return today’s courses, the current course, and the selected week’s timetable.

The frontend calls `/query/overview` to load the dashboard in one request, which reduces repeated calls and keeps the page responsive.

The module also includes an asynchronous schedule-fetch task interface for the SCNU academic system. The task status is stored and can be polled by the frontend.

Here’s how it works: the user initializes a semester with a semester name and start date. The backend creates or updates a schedule JSON file for the current student. When a course is added, the service validates the period range and week list. The storage layer assigns a UUID to the course, sorts courses by weekday and period, and writes the updated schedule back to disk. The dashboard reloads `/query/overview`, which returns the schedule, current course, today’s courses, and week timetable together.

For week calculation, the service compares today’s date with the semester start date. The difference in days is divided by seven to get the teaching week number. After that, courses are filtered by weekday, active week list, and week type.

The schedule-fetch feature is implemented as an asynchronous task. When the frontend submits `/schedule/fetch`, the backend creates a task ID, marks it as `queued`, and starts a background thread. The task later becomes `running`, `succeeded`, or `failed`, so the frontend can show progress without blocking the page.

---

## 5. Required Data Structures

The project follows the object-oriented programming course requirement by implementing custom data structures.

The hash table is used for fast user and session lookup, which matches the authentication use case since almost every protected request needs to check a session token.

The queue is used for task-style workflows, like academic schedule fetching. A queue works well here because these tasks should be processed in order.

The binary search tree and doubly linked list are part of the schedule data-structure design. They support indexed course access and ordered traversal concepts required by the course design.

Even where the application also uses normal Python lists for practical API output, the custom structures are implemented, tested, and connected to the project design.

The hash table is implemented with buckets and collision handling, so it's suitable for key-value access like `student_id -> user` and `token -> session`.

The queue provides first-in-first-out behavior and is used as the conceptual model for scheduled background work.

The doubly linked list supports forward and backward traversal, which is useful for demonstrating ordered course traversal and navigation-style operations.

The binary search tree stores searchable keys and supports insert, search, and traversal operations. In the schedule design, the natural key is based on time, like weekday and period.

These structures aren't just written as separate files. They also have dedicated tests that verify normal cases, missing values, empty structures, insertion, deletion, and traversal behavior.

---

## 6. Note Processing Module

The note module turns uploaded documents into structured learning material.

When a student uploads a PDF or DOCX file, the backend saves the original file first, then extracts text from the document. PDF extraction uses `pdfplumber`, and DOCX extraction uses `python-docx`.

After text extraction, the service splits the note into chunks. It recognizes common heading formats like numbered headings, Chinese chapter headings, and Markdown-style headings. Long sections are split again with a fixed maximum length and overlap.

This chunk design matters because search, question answering, and graph generation work better on smaller units than on an entire document.

The original file, note metadata, and chunks are kept separately, which makes preview, editing, search, and deletion easier to manage.

The upload pipeline is one of the more important technical flows in the project. The router receives a multipart file through `/note/upload` and accepts an optional `course_id`, so the note can be attached to a specific course immediately. `NoteService` validates the file type—only PDF and DOCX are accepted. The original file is saved under the note file directory using a generated note ID, which prevents filename conflicts.

Then the service extracts text. For PDF, it loops through pages with `pdfplumber` and collects extracted text. For DOCX, it reads paragraphs with `python-docx` and keeps non-empty paragraph text.

Next, the text is chunked. The chunker scans line by line and detects headings with several regular expressions. It supports Markdown headings, numbered headings, Chinese chapter-style headings, and uppercase English headings. If there's no clear heading, it falls back to fixed-size windows.

Each chunk is saved with a `chunk_id`, `note_id`, heading, content, and chunk index. The note metadata and chunks are stored in SQLite, while the original file stays on disk for preview and download.

After upload, the system tries several best-effort enhancements: indexing chunks, generating a title and summary, and auto-assigning the note to a topic. If any of these optional steps fail, the upload itself still succeeds, which makes the feature much more robust during demonstrations.

---

## 7. Knowledge Tree, Search, and Graph

The knowledge workspace adds a topic tree on top of normal note storage.

A topic has a name, summary, keywords, parent topic, child topics, and related note IDs. Students can organize notes by real course concepts instead of only by file names.

The search feature can use vector retrieval when the vector service is available. The system is also designed with a lexical fallback, so the prototype still works during local testing or when external model services are unavailable.

For topic routing, the system can rank topics based on a query. If a student searches for “Euler circuit”, the graph can focus on the Graph Theory topic instead of showing every note.

The graph API returns nodes and links. Nodes represent note chunks, and links represent similarity between chunks. The frontend renders the graph with Cytoscape, which supports interactive visualization in the browser.

The knowledge tree is stored per student and per course, which matters because each student can have a different set of topics, and the same student may organize different courses in different ways.

Topic operations include create, update, delete, assign note, and unassign note. When a topic is deleted, child topics and assigned notes are handled carefully so the tree doesn't break.

Search has two layers. The preferred layer is vector search through `mem0`, Qdrant, and a multilingual sentence-transformer model, which allows semantic search where the query doesn't need to exactly match the note text.

The fallback layer is lexical search. It tokenizes the query and candidate text, calculates overlap, and gives an additional score when one text contains the other. It's less powerful than vector search, but it's deterministic, fast, and reliable in local tests.

The graph-building process works like this: load notes and chunks for the current student and course. If the user provides a topic or query, rank the most relevant topics. Select only notes under those topics when topic routing is applied. Convert chunks into graph nodes. Build links between similar chunks, using vector similarity when available and lexical similarity as a fallback. Return a graph response with nodes, links, selected topic IDs, routing status, and counts.

Topic routing keeps the graph readable. Instead of always comparing every note with every other note, it narrows the graph to the most relevant part of the course.

---

## 8. AI and External Service Strategy

The system is designed to work with DeepSeek through the OpenAI-compatible SDK.

The LLM can generate note summaries and answer questions based on retrieved note chunks.

At the same time, the implementation doesn’t make the whole system depend on the LLM. If the API key is missing or the model service is unavailable, the application still returns relevant source chunks.

This fallback strategy improves reliability and makes the prototype easier to demonstrate in different environments.

There are two main LLM use cases. The first one is summary generation. After upload, the service takes the first few chunks and asks the model to return a title and a short summary. The result is written back to the note metadata.

The second one is question answering. The system first retrieves related chunks, then builds a prompt that tells the model to answer based on the note content. It’s a retrieval-augmented generation flow, so the answer is grounded in the student’s own uploaded materials.

The code checks whether the API key is configured before using the LLM. If it’s not configured, the system returns retrieved source chunks instead of crashing, which is important because classroom demos often run without stable external API access.

---

## 9. Frontend Design

The frontend is built as a multi-page Vue 2 application.

The login page handles registration and login.

The dashboard page focuses on schedule use: current course, today’s courses, weekly timetable, semester setup, schedule import, academic-system fetch, and manual course editing.

The knowledge workspace page focuses on learning materials: topic tree, note upload, document preview, chunk list, search, question answering, and knowledge graph.

The pages are designed around real student workflows. A user can start from the timetable, click into a course, and immediately manage notes for that course.

The dashboard page is driven mainly by `/query/overview`. That endpoint gives the page enough data to render the current course card, today’s list, the weekly timetable, and the schedule status.

The knowledge workspace has three columns. The left column manages the topic tree. The center column manages note upload, note selection, metadata editing, preview, and chunks. The right column handles question answering, chunk search, graph controls, and graph rendering.

The frontend uses the same backend course ID when moving from the timetable to the knowledge workspace, which keeps the user in the correct course context and avoids manual filtering after navigation.

---

## 10. Persistence and Practical Data Handling

The system stores runtime data locally.

Users and schedules are stored as structured files. Notes use SQLite for metadata and chunks, which is more suitable for filtering, listing, and joining note records.

Uploaded files are kept in a dedicated file directory, while knowledge-tree data is stored separately by user and course.

This approach is lightweight and easy to run for a course project. It avoids the setup cost of a full database server, but still gives the system enough persistence for real browser testing.

Schedule data is stored as JSON because the schedule object is naturally document-shaped: one student, one semester, and a list of courses.

Note metadata and chunks use SQLite because notes need more flexible queries. The system often needs to list notes by student, filter notes by course, join chunks with their parent notes, and delete chunks when a note is deleted.

Uploaded files are stored separately because they're binary assets. Keeping them out of the metadata database makes preview and download simpler.

Knowledge trees are stored separately from note files and note chunks, which keeps the learning structure independent from the raw documents, so a note can be reassigned or reorganized without re-uploading the file.

---

## 11. Testing and End-to-End Validation

The project includes unit tests, API tests, integration tests, and a browser end-to-end test.

Unit tests cover core data structures and service logic.

API tests cover authentication, schedule creation, query endpoints, page guards, and request logging.

The note and knowledge integration tests cover a realistic Discrete Mathematics scenario. They create a course, create topics, upload DOCX notes, assign notes to topics, search for concepts, and build a topic-routed graph.

The browser E2E test goes through the actual user interface with Playwright. It registers and logs in, creates a schedule, adds a course, opens the knowledge workspace, uploads notes, links notes to topics, searches chunks, and refreshes the graph.

This gives us confidence that the prototype works as a complete user flow, not only as isolated backend functions.

The integration scenario uses Discrete Mathematics because it's realistic and easy to verify. It creates topics like Propositional Logic, Relations and Partial Orders, and Graph Theory. Then it uploads DOCX notes about truth tables, partial orders, and Euler circuits.

The tests verify that a search for truth tables returns the logic note, and a graph query about Euler circuits routes to the Graph Theory topic. This is stronger than simply checking whether an endpoint returns `200`, because it checks whether the feature produces meaningful results.

The tests also isolate runtime data in temporary directories, which prevents test runs from polluting real user data and makes the test suite repeatable.

---

## 12. Git Version Management and Team Collaboration

The project also shows organized Git management.

The repository history includes feature branches, merges, and focused commits. Examples include backend service work, frontend integration, logging refactoring, dependency updates, and full-link integration testing.

The documentation defines clear branch responsibilities, like backend service development and frontend development. It also warns against risky operations like force push or hard reset.

The codebase follows clear ownership boundaries. Core data structures, storage, services, routers, frontend pages, and tests are placed in separate directories.

This structure helps team members work in parallel. A frontend member can adjust Vue pages while a backend member improves services or tests, as long as the API contract stays stable.

The collaboration process is supported by documentation. `README.md` explains setup, branch usage, coding style, testing expectations, and risky Git operations to avoid. `FRONTEND_API.md` records the API contract used by the frontend. The design documents explain the architecture and implementation priorities.

This reduces communication cost. When a backend endpoint changes, the team knows the frontend API document should be updated. When a feature is added, the team knows tests should be added or adjusted.

The Git history also shows progressive integration. There are commits for service features, frontend integration, logging refactoring, dependency updates, and full-link browser testing. It reflects a normal team workflow rather than one final large commit.

---

## 13. Realistic Scenario and Practical Value

The prototype is based on a realistic student scenario.

A student first needs a reliable timetable. Then, during the semester, they collect course notes. Later, they need to find concepts quickly, connect related topics, and review before exams.

Our system supports that full path.

The schedule dashboard helps with daily course planning. The knowledge workspace helps organize materials after class. Search and graph features help review and discover relationships between concepts.

Because the system uses real browser pages, real uploaded documents, persistent storage, and tested API flows, it's more than a static mockup. It's a working prototype with practical value.

---

## 14. Closing

So that's the project. It combines schedule management, document processing, knowledge organization, and browser-based interaction.

Technically, it demonstrates layered FastAPI design, custom data structures, file and SQLite persistence, document chunking, retrieval, graph construction, robust fallback behavior, and automated testing.

From a teamwork perspective, the project has clear documentation, stable API contracts, meaningful tests, and a Git history that reflects collaborative development.

The result is a prototype that satisfies course requirements while also solving a real student use case in a practical way.
