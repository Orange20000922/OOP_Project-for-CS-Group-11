# Prototype Demo Video Script

## Purpose

This script is for a short product-style demo. The tone should be clear, natural, and slightly conversational. The presenter can speak while another team member operates the browser.

Suggested length: 3 to 5 minutes.

---

## Scene 1: Opening

**Camera / Screen**

Show the browser at the login page.

**Narration**

Hi everyone. Today we're showing you our student schedule and course knowledge workspace prototype.

It's basically a tool that helps students manage their weekly timetable and turn their course notes into a searchable knowledge base.

The workflow's pretty straightforward: you log in, set up your schedule, add courses, and then each course gets its own knowledge workspace where you can upload notes, organize them by topic, and search through everything.

---

## Scene 2: Register and Log In

**Camera / Screen**

Switch to register mode. Fill in a student name, student ID, SCNU account, and password. Submit the form.

**Narration**

Let's start by creating an account.

You use your student ID as the main identifier. There's also an optional SCNU account field if you want to import schedules directly from the university system later.

Once we're registered, we can log in. The system uses session cookies, so you stay logged in as you navigate around.

**On-screen action**

After successful login, the page redirects to the schedule dashboard.

---

## Scene 3: Schedule Dashboard

**Camera / Screen**

Show the dashboard page. Point to the current course card, today course list, weekly timetable, and right-side control panels.

**Narration**

Here’s the schedule dashboard.

On the left, you’ve got your student view: what class you’re in right now, what’s on today, and your full weekly timetable.

The right side is where you manage things. You can set up the semester, upload a schedule file, fetch from the academic system, or manually add and edit courses.

If you haven’t created a schedule yet, you’ll see an empty state prompting you to initialize the semester first.

---

## Scene 4: Initialize Semester

**Camera / Screen**

Enter:

- Semester: `2025-2026-2`
- Start date: `2026-03-02`

Click the save button.

**Narration**

Let's initialize the semester.

The start date matters because it's how the system figures out what week we're in. That way the dashboard can show you the right courses for this week.

---

## Scene 5: Add a Course Manually

**Camera / Screen**

Use the course form to add a sample course:

- Course: Discrete Mathematics
- Teacher: Teacher Zhou
- Location: Science Building B201
- Weekday: Tuesday
- Period: 3 to 4
- Weeks: 1-20
- Week type: All weeks

Submit the form.

**Narration**

Let's add a course manually.

You fill in the course name, teacher, classroom, weekday, time slots, which weeks it runs, and whether it's every week or just odd/even weeks.

Once you save it, the course shows up in your course list and on the weekly timetable. Both views pull from the same data, so editing or deleting a course updates everything.

**Camera / Screen**

Click previous week and next week.

**Narration**

You can navigate between weeks to see what's coming up. The system recalculates which courses are active for whichever week you're looking at.

---

## Scene 6: Enter the Knowledge Workspace

**Camera / Screen**

Click “Knowledge Workspace” from the course card or the course list.

**Narration**

Each course has its own knowledge workspace.

Instead of keeping notes scattered across different folders, you can upload them here and search through everything later.

---

## Scene 7: Knowledge Workspace Overview

**Camera / Screen**

Show the top area: course title, course selector, note count, topic count, chunk count, graph node count.

**Narration**

This is the course knowledge workspace.

At the top, you can see which course you're in and some quick stats: how many notes, topics, chunks, and graph nodes you have.

The page has three main sections. Left side manages your knowledge tree. Middle section is for uploading and previewing notes. Right side is where you search, ask questions, and view the knowledge graph.

---

## Scene 8: Create Knowledge Topics

**Camera / Screen**

Create three topics:

- Propositional Logic
- Relations and Partial Orders
- Graph Theory

Use short summaries and keywords.

**Narration**

Before uploading notes, let's create some knowledge topics.

Think of these as a structured outline for the course. Each topic can have a name, summary, keywords, and even a parent topic if you want to nest them.

It's more useful than just having a flat list of files. You can group notes by concept, and later the graph can focus on specific topic areas.

---

## Scene 9: Upload Notes

**Camera / Screen**

Upload DOCX files such as:

- `logic.docx`
- `relation.docx`
- `graph.docx`

After each upload, select the note and assign it to the matching topic.

**Narration**

Now let's upload some course notes.

The system supports PDF and DOCX files. When you upload something, it saves the original file, extracts the text, and splits it into smaller chunks.

Each note card shows the filename, file type, when it was updated, how many chunks it has, and a summary if one's been generated.

You can also assign notes to topics. So here, the logic note goes under Propositional Logic, the relation note under Relations and Partial Orders, and the graph note under Graph Theory.

---

## Scene 10: Preview and Edit Notes

**Camera / Screen**

Click one note. Show metadata fields, preview area, and chunk list.

**Narration**

When you select a note, you can edit its title, summary, and which course it belongs to.

The original document shows up in the preview area. For DOCX files, you get a readable preview right in the browser. For PDFs, you can open the uploaded file.

On the side, you'll see the extracted chunks. These are what get used for search, question answering, and graph generation.

---

## Scene 11: Search Note Chunks

**Camera / Screen**

Search for a term such as `truth table`.

Click the search button and show the result cards.

**Narration**

Let's try searching inside the notes.

Say we search for “truth table”. The system returns the most relevant chunks and shows which note each result comes from.

Pretty handy when you remember a concept but can't remember which file it's in.

---

## Scene 12: Ask a Question

**Camera / Screen**

Ask a question such as:

`What is a truth table used for?`

Show the answer and source chunks.

**Narration**

There’s also a question-answering panel.

The system grabs related chunks from your notes. If you’ve got an LLM service configured, it’ll generate an answer based on those chunks. If not, you still get the relevant source text, so it’s still useful.

We designed it this way so the prototype works even without a stable API connection.

---

## Scene 13: Knowledge Graph

**Camera / Screen**

Enter a graph query such as `Euler circuit`, then click refresh graph.

Show graph tags such as routed topic names, node count, and edge count. Show the graph canvas.

**Narration**

Finally, let's generate a knowledge graph.

The graph shows note chunks as nodes and connects related chunks with edges.

When you enter a query, the system can route the graph to the most relevant topic. So a query about Euler circuits focuses on the Graph Theory topic instead of showing everything.

It helps you explore relationships between concepts without reading every file from start to finish.

---

## Scene 14: Closing

**Camera / Screen**

Return briefly to the dashboard, then back to the knowledge workspace.

**Narration**

So that's the prototype. It connects three workflows: managing your course schedule, linking each course to a knowledge workspace, and turning your notes into searchable, structured learning material.

It's still a prototype, but it already shows a complete path from schedule management to note organization and knowledge visualization.

