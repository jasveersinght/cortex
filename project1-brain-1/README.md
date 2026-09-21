# JA Assure Compliance Agent

This repository contains the compliance agent for JA Assure's AI marketing pipeline.
It is the core gate that every generated marketing asset (caption, post, script) must
pass through before it becomes eligible for human approval and publishing.

The compliance agent evaluates each draft asset from four independent angles, produces
a single confidence score, and routes the asset into one of four review tiers. Every
human decision made afterward (approve, edit, reject) is captured as a lesson and used
to improve future content generation. This document explains what the agent does, how
the code is organized, how to set it up, and how to push it to GitHub.

## 1. What the compliance agent does

Insurance marketing is a regulated activity. Certain claims cannot legally be made in
promotional content (for example, guaranteeing a payout or implying there are no
exclusions). The compliance agent checks every generated asset against a written rubric
before it is allowed to move forward in the pipeline.

The agent does this using four separate checks, referred to as lenses:

1. Claims Lens: checks for prohibited or absolute language, such as guaranteed payouts
   or claims of zero exclusions.
2. Regulatory Lens: checks the asset against region-specific insurance advertising rules
   for Singapore, Malaysia, Hong Kong, Indonesia, and Thailand.
3. Brand Lens: checks that the tone and language match the correct brand voice for Jade,
   Jaguar Transit, or DoctorShield.
4. Accuracy Lens: checks that any specific factual claim made in the asset is consistent
   with the underlying policy information provided, and flags unverifiable claims when
   no source is given.

Each lens returns a score from 0 to 100, a list of flagged phrases, and a short reason
explaining the score. These four scores are combined using a weighted average, where the
Accuracy and Regulatory lenses are weighted more heavily because they carry the highest
legal and factual risk. The result is a single confidence score for the asset.

Based on the confidence score, the asset is placed into one of four tiers:

- 85 to 100: Highly Recommended. The asset is considered safe and is fast-tracked for
  human approval.
- 65 to 84: Recommended, Review Needed. The asset is likely acceptable but a human should
  confirm the flagged points before approval.
- 40 to 64: Vigilant, Review Immediately. The asset has multiple concerns and should be
  reviewed as a priority.
- 0 to 39: Suspicious. The asset is automatically rejected and is not shown to a human
  as pending; the rejection and its reasons are logged directly.

A human reviewer works through the pending assets, tier by tier, using the dashboard.
For every asset that is edited or rejected, the reviewer must record a short reason tag,
for example "too salesy", "inaccurate claim", "off-brand tone", or "wrong CTA". These
reasons are stored as lessons learned. The next time the content agent generates a new
asset for the same brand, it is shown the most recent lessons as guidance, so it does
not repeat the same mistake. Over time, the rejection rate and average confidence score
can be tracked to demonstrate that the system is improving.

## 2. Repository structure

```
project1-brain/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── db.py
├── agents/
│   ├── content_agent.py
│   ├── compliance_gate.py
│   └── feedback_agent.py
├── rubrics/
│   └── rules.md
├── dashboard/
│   └── review.py
└── main.py
```

File descriptions:

- db.py: creates and connects to the SQLite database. Defines three tables: assets,
  lens_scores, and lessons_learned.
- agents/content_agent.py: generates a draft marketing asset using the Grok API, taking
  brand, platform, content type, topic, and region as input. Injects recent lessons
  learned for that brand into the prompt.
- agents/compliance_gate.py: the compliance agent itself. Runs the four lenses, combines
  their scores, assigns a tier, and stores the results in the database.
- agents/feedback_agent.py: records human review decisions, stores lesson tags, and
  provides functions to calculate rejection rate and average confidence score over time.
- rubrics/rules.md: the written compliance rubric used by all four lenses. This file can
  be edited directly to change the rules without touching any code.
- dashboard/review.py: a command-line interface for a human reviewer to view pending
  assets by tier, see the lens breakdown for each, and approve, edit, or reject them.
- main.py: runs the full pipeline for a single asset, from generation through the
  compliance gate.

## 3. Where to place the Grok API key

The Grok API key must never be written directly into any code file or committed to
GitHub. It is loaded from an environment file that stays only on your local machine.

Steps:

1. In the root of the project, locate the file named `.env.example`.
2. Make a copy of this file in the same location and rename the copy to `.env`.
   On Mac or Linux, this can be done with:
   ```
   cp .env.example .env
   ```
   On Windows (Command Prompt):
   ```
   copy .env.example .env
   ```
3. Open the new `.env` file in a text editor.
4. Go to https://console.x.ai and generate an API key from your account.
5. Replace `your_key_here` in the `.env` file with the real key, so the line reads:
   ```
   GROK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. Save the file.

The `.env` file is already listed in `.gitignore`, which means Git will not track it
and it will not be pushed to GitHub. Only `.env.example`, which contains no real key,
is committed.

## 4. Setup and running locally

1. Install Python 3.10 or later.
2. From the project root, install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Complete the API key setup described in Section 3.
4. Initialize the database:
   ```
   python db.py
   ```
   This creates a local file named `ja_assure.db` with all required tables.
5. Run the pipeline for one sample asset generation and compliance check:
   ```
   python main.py
   ```
   Edit the brand, platform, content_type, topic, and region arguments at the bottom
   of `main.py` to generate different assets.
6. Review generated assets through the dashboard:
   ```
   python dashboard/review.py
   ```
   This lists all pending assets grouped by tier, shows the lens breakdown for each,
   and prompts for an approve, edit, or reject decision with a reason tag when needed.

## 5. How to push this code to GitHub

Follow these steps from the root of the project folder, in order.

1. If Git is not already installed, install it first and confirm with:
   ```
   git --version
   ```
2. Initialize a Git repository in the project folder, if not already done:
   ```
   git init
   ```
3. Confirm that `.env` and `*.db` are listed in `.gitignore` so secrets and local
   data are never committed. Check the file:
   ```
   cat .gitignore
   ```
4. Stage all project files:
   ```
   git add .
   ```
5. Confirm what is about to be committed, and verify `.env` and `ja_assure.db` are
   not in the list:
   ```
   git status
   ```
6. Create the first commit:
   ```
   git commit -m "Initial commit: JA Assure compliance agent"
   ```
7. Create a new empty repository on GitHub through the GitHub website. Do not
   initialize it with a README, license, or .gitignore, since these already exist
   locally.
8. Copy the repository URL shown on GitHub after creation. It will look like:
   ```
   https://github.com/your-username/your-repo-name.git
   ```
9. Link the local repository to the GitHub repository:
   ```
   git remote add origin https://github.com/your-username/your-repo-name.git
   ```
10. Rename the local branch to main, if it is not already:
    ```
    git branch -M main
    ```
11. Push the code to GitHub:
    ```
    git push -u origin main
    ```
12. Enter your GitHub username and a personal access token when prompted for a
    password. GitHub no longer accepts account passwords for this step. A personal
    access token can be created under GitHub account settings, in the Developer
    Settings section, under Personal Access Tokens.

After this, the repository is live on GitHub. For any future changes, the workflow is:
```
git add .
git commit -m "Description of the change"
git push
```

## 6. Editing the compliance rubric

The rules used by all four lenses live in `rubrics/rules.md` as plain text. To change
what is flagged or how strict a lens is, edit this file directly. No code changes are
required, since the compliance agent reads this file fresh on every run.

## 7. Notes on the scoring weights

The weighted average used to compute the final confidence score is defined in
`agents/compliance_gate.py` in the `LENS_WEIGHTS` dictionary:

```
claims: 20 percent
regulatory: 30 percent
brand: 15 percent
accuracy: 35 percent
```

These weights reflect that factual accuracy and regulatory compliance carry the
highest legal risk, while brand tone carries the lowest. These weights can be
adjusted directly in the code if a different balance is needed.