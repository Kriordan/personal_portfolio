# Project: Engineering Learning & Mastery Platform

## Context and Vision

I want to substantially expand the existing Learning tool in my `personal_portfolio` repository.

The repository includes a Flask API, Flask website, Expo React Native application, and PostgreSQL database.

I have approximately 10–11 years of software engineering experience, primarily in full-stack development. I'm largely self-taught and have practical production experience, but I want to rebuild and strengthen my computer science fundamentals, technical vocabulary, system design skills, application architecture knowledge, and engineering judgment.

My goal is to become an exceptionally capable senior software engineer, eventually operating comfortably at staff-level depth, and remain effective as AI transforms software engineering over the coming years.

**I do not want to build a conventional flashcard application.**

I want to build a personal, interactive engineering education and mastery platform that combines the strengths of:

- A well-structured technical textbook
- An interactive visual learning environment
- A spaced-repetition system
- A coding and problem-solving practice environment
- An AI technical mentor
- A simulated senior/staff engineering interview and collaboration environment

The platform should help me progress through four levels:

1. **Recognition:** I recognize the terminology and concepts.
2. **Understanding:** I can explain how something works and why it matters.
3. **Application:** I can implement it, debug it, or use it to solve a problem.
4. **Judgment:** I can evaluate alternatives, anticipate failures, defend trade-offs, and communicate decisions effectively.

The ultimate measure of success is not how much content I consume, but what I can reliably explain, build, and reason about without assistance.

## Your Assignment

**This is a planning task only. Do not modify files or implement anything yet.**

First, inspect the existing repository thoroughly, especially the Learning tool.

Understand the established application architecture, existing data models, migrations, APIs, UI components, learning functionality, authentication, and patterns.

Then design the smallest maintainable architecture that can grow into the platform described below.

Reuse existing functionality whenever appropriate. Do not propose a wholesale rewrite unless the existing design genuinely cannot support the requirements.

---

# 1. Four Core Learning Experiences

The platform should support four complementary learning modes.

## Mode A: Learn

Purpose: Develop deep understanding of technical concepts.

The fundamental educational unit should be a **Concept**, not a flashcard.

A concept may include:

- A concise explanation in accessible language
- A deeper technical explanation
- Interactive diagrams and visualizations
- Architecture and sequence diagrams
- Code examples and walkthroughs
- Real-world examples of production usage
- Common misconceptions
- Failure modes and troubleshooting
- Comparisons with related techniques
- Performance, security, and reliability considerations
- Architectural trade-offs
- Prerequisites and related concepts
- Trusted references and further reading
- Content versioning and review dates

Allow progressive disclosure. Someone learning the concept for the first time may need a detailed walkthrough, while someone revisiting it should be able to refresh their memory quickly.

Not every concept requires every content type. Choose representations based on their educational usefulness.

Favor diagrams and source-controlled visualizations when appropriate, not decorative images.

## Mode B: Review

Purpose: Retain knowledge through retrieval practice.

Support:

- Spaced repetition
- Short-answer recall
- Concept comparisons
- Scenario-based questions
- Identifying misconceptions
- Explaining trade-offs
- Self-assessment
- Progress and mastery tracking

Investigate FSRS or other proven spaced-repetition approaches, but check whether the existing application already implements appropriate functionality.

Review should remain lightweight and fast. It should not require rereading complete lessons.

The system should distinguish factual recall from deeper conceptual mastery.

## Mode C: Discuss

Purpose: Build engineering judgment, communication skills, and confidence.

This is a major requirement, not an optional afterthought.

I want to have realistic technical conversations with an AI counterpart, ideally through text initially and natural spoken interaction eventually.

Support several exercise types:

**Guided technical coaching**

The AI helps me understand a concept through Socratic questioning, examples, counterexamples, and targeted hints.

**System design interview**

The AI presents an architectural problem and plays the role of a technical interviewer.

I should be expected to:

- Ask clarifying questions
- Identify functional and nonfunctional requirements
- Discuss assumptions and constraints
- Estimate scale where appropriate
- Propose an architecture
- Define APIs and data models
- Consider reliability, scalability, security, and observability
- Identify bottlenecks and failure modes
- Compare alternative approaches
- Defend architectural trade-offs

The interviewer should challenge my choices without immediately providing answers.

**Engineering scoping / grooming meeting**

Simulate working with senior and staff engineers to scope an unfamiliar feature or system.

This should feel collaborative rather than like an interview.

I want to practice:

- Turning vague requirements into concrete specifications
- Discovering hidden assumptions and dependencies
- Asking productive questions
- Exploring alternatives
- Estimating complexity and identifying risks
- Negotiating scope and constraints
- Decomposing work into implementation milestones
- Communicating technical decisions

**Technical debate / design review**

Present an existing architecture or proposed solution and challenge me to critique it, propose improvements, and explain the trade-offs.

Distinguish between coaching, interviewing, and collaborative discussion. They require different interaction styles and evaluation criteria.

### Discussion feedback

At the end of each exercise, provide structured, constructive feedback.

Evaluate dimensions such as:

- Technical correctness
- Requirements discovery
- Architectural reasoning
- Identification of trade-offs
- Handling of edge cases and failure scenarios
- Communication and clarity
- Depth of understanding
- Awareness of uncertainty

Provide concrete examples from my responses explaining what I did well, what I missed, and how I might improve.

Do not present subjective AI-generated scores as authoritative measurements of engineering ability.

Use transparent rubrics and evidence from the actual discussion. Distinguish confirmed mistakes from debatable design decisions.

Link identified knowledge gaps back to relevant concepts in the curriculum.

### Conversation modalities

Design the underlying discussion/exercise model so it can eventually support:

- Typed conversations
- Speech-to-text responses
- Real-time spoken conversation
- Optional audio recordings and transcripts
- Pausing, resuming, and reviewing sessions
- Post-session feedback and summaries

Investigate the technical options, architecture, cost, latency, reliability, and privacy implications of voice.

**Do not require a sophisticated real-time voice implementation for the initial pilot.** A text-based discussion simulator should be sufficient to validate the educational value.

## Mode D: Build

Purpose: Demonstrate knowledge through implementation and problem-solving.

Support different forms of technical work:

- Pseudocode solutions
- Python and TypeScript coding exercises
- Algorithmic reasoning
- Database queries and schema design
- API design
- Debugging exercises
- Refactoring exercises
- Code review exercises
- Small implementation challenges
- Architecture and technical design documents

Eventually I want an editor that can accept, validate, and evaluate code, potentially including automated tests.

For the initial pilot, a simple code or pseudocode submission interface with saved responses and structured feedback may be sufficient.

Investigate an approach that supports richer coding exercises later without prematurely building a full online IDE.

If executable code is introduced, explicitly address isolation, resource limits, security, test execution, and operational cost.

---

# 2. Curriculum Architecture

Develop a comprehensive senior software engineering curriculum emphasizing durable, transferable knowledge.

Initial subject areas should include:

1. Computer science fundamentals
2. Data structures and algorithms
3. Networking, HTTP, and communication protocols
4. Operating systems, concurrency, and execution models
5. Database design and internals
6. Application architecture and API design
7. Distributed systems
8. System design and scalability
9. Cloud infrastructure and deployment
10. Reliability, observability, and performance
11. Security and authentication/authorization
12. Testing and software quality
13. AI-assisted engineering, LLM systems, and evaluation
14. Technical leadership, collaboration, and engineering judgment

Use my existing stack—Python, Flask, TypeScript, React Native, and PostgreSQL—where practical examples would be useful, but don't restrict the curriculum to those technologies.

Aim initially for approximately **200–300 rich concepts**, with potentially **600–1,200 review questions**, but treat those as planning estimates rather than fixed quotas.

Design a hierarchy of domains, topics, concepts, and prerequisite relationships.

Recognize that concepts have different depths. Some merit a five-minute explanation; others justify a substantial technical lesson and multiple exercises.

Consider an initial diagnostic assessment to identify strengths, weaknesses, and prerequisite gaps, rather than requiring experienced engineers to study everything linearly.

## Content quality

The curriculum should be technically rigorous.

Plan for:

- Trusted primary references and documentation
- Source attribution
- Technical fact-checking
- Duplicate detection
- Consistent terminology
- Clear prerequisites
- Validated code examples
- Human review before publishing substantial AI-generated batches
- Content versioning
- Periodic reassessment of fast-changing subjects
- Preserving progress when content changes

Prefer quality and depth over the quantity of generated content.

---

# 3. Data and Content Architecture

Evaluate how the existing application should store and render concepts, learning resources, questions, exercises, conversations, submissions, feedback, and user progress.

Consider maintaining canonical educational content in version-controlled Markdown/YAML/JSON files, with a repeatable process for importing or synchronizing it into PostgreSQL.

Do not assume this is the best solution without reviewing the repository.

Maintain clear separation between:

- Canonical curriculum content
- Learning resources and visualizations
- Review questions and exercises
- Conversation/exercise templates
- Individual learning sessions
- User submissions and transcripts
- AI-generated feedback
- Mastery and spaced-repetition history

Use stable identifiers and content versions.

Ensure that revising a concept does not unnecessarily erase learning progress.

Consider provenance, portability, and vendor independence.

---

# 4. AI Architecture

Investigate the smallest reasonable way to support AI-powered coaching, simulated conversations, and evaluation.

Address:

- LLM integration and provider abstraction
- Prompt templates and versioning
- Persisted session context
- Role and behavior configuration
- Structured exercise rubrics
- Deterministic validation where possible
- Hallucination and incorrect-feedback mitigation
- Streaming responses if useful
- Cost per session and monthly cost estimates
- Latency and reliability
- Handling failed or interrupted sessions
- Privacy and retention of conversations and recordings

Distinguish between deterministic educational logic and tasks that genuinely benefit from AI.

For example, spaced-repetition scheduling should not require an LLM call.

Likewise, where tests can objectively verify a code submission, use them rather than relying entirely on AI judgment.

Explore how feedback from discussions and implementation exercises might inform future review priorities without blindly treating model-generated evaluations as ground truth.

---

# 5. Product Experience

Investigate how these experiences should work in the existing web and Expo applications.

I want something practical for daily use, not an elaborate administrative system.

Consider a workflow such as:

1. Open Learning.
2. See due reviews and suggested learning activities.
3. Review existing material.
4. Study a new concept.
5. Work through a related exercise.
6. Receive targeted feedback.
7. Return later to reinforce weak areas.

Consider connecting multiple learning experiences around one concept.

For example, studying idempotency could lead to:

- A visual explanation of retries
- A short recall exercise
- A system design discussion about duplicate payment requests
- A coding exercise implementing an idempotent API endpoint
- A follow-up review targeting any misconceptions

Explore an approachable progress display that reflects both retention and applied proficiency.

Avoid gamification that encourages superficial completion over understanding.

Account for the differences between desktop and mobile interaction. Long coding and architecture exercises may be better suited to desktop, while short lessons and reviews should work comfortably on mobile.

---

# 6. Implementation Strategy

I want incremental delivery, not a multi-month infrastructure project before anything is usable.

Propose a vertical-slice pilot with approximately:

- 10–15 high-value concepts
- 30–50 carefully developed review questions
- A handful of representative technical scenarios
- A basic text-based technical discussion experience
- A simple pseudocode/written-solution submission experience
- Saved session results and feedback
- Integration with existing learning and progress functionality

The pilot should validate whether the platform actually helps me learn, remember, explain, and apply technical concepts.

Explicitly identify which features are essential to the first implementation and which should be deferred.

Propose subsequent milestones for:

- Expanded curriculum content
- More sophisticated assessments
- Deeper engineering discussions
- Improved coding exercises and automated tests
- Real-time voice and recording
- Multi-participant simulated meetings
- Personalized study recommendations
- Long-term curriculum maintenance

The roadmap should preserve the long-term vision without forcing us to build every feature upfront.

---

# 7. Your Planning Deliverables

After inspecting the repository, provide:

1. **Existing architecture assessment:** What the Learning tool already supports and what can be reused.

2. **Recommended product architecture:** How the four experiences fit together.

3. **Data model proposal:** Core entities, relationships, content formats, and persistence strategy.

4. **Curriculum taxonomy:** Proposed domains and prerequisite organization.

5. **Example concept:** Show how one complete concept could support Learn, Review, Discuss, and Build.

6. **AI interaction design:** How technical conversations, session state, feedback, and evaluations should work.

7. **Implementation roadmap:** Small, ordered milestones with dependencies and explicit acceptance criteria.

8. **Pilot scope:** What the first usable version should contain and how to validate it.

9. **Risks and trade-offs:** Complexity, cost, content accuracy, technical limitations, user experience, and vendor dependencies.

10. **Open questions:** Decisions I need to make before implementation.

11. **Verification strategy:** How we will test application behavior, educational content, and AI-generated feedback.

12. **Work division:** Which work Codex should implement in the repository versus which research and content-development tasks would benefit from ChatGPT Work.

Where requirements conflict, favor a small, high-quality, maintainable implementation that delivers genuine educational value.

Do not overengineer the system for hypothetical future needs, but avoid obvious architectural dead ends.

**Important: Do not implement anything yet. Produce the plan, explain the key trade-offs, and wait for my approval before making changes.**

The final objective is to build a system that improves my ability to understand, design, implement, critique, and communicate about production software—not merely memorize terminology.