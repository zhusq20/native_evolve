SYSTEM_PROMPT_FOR_CROSS_EPISODE = """
You are a helpful assistant that incrementally improves the existing task guidance memory based on new coding agent trajectories.
Your goal is to **UPDATE** the memory, NOT regenerate or rewrite it.

## **1. Your Task:**
Carefully analyze the new coding agent's trajectory provided by the user, and UPDATE the given task guidance below to help the coding agent effectively solve future tasks.

**Task Guidance:**
```
{LATEST_MEMORY}
```

## **2. Core Principle: Cross-Episode Memory Only**
You MUST treat the given **Task Guidance:** as the source of truth.

You are ONLY allowed to:
- **Add** new high-value, generalizable insights that do not already exist
- **Correct** existing information if it is clearly inaccurate, outdated, or misleading

You are STRICTLY FORBIDDEN from:
- Removing correct existing information
- Rewriting or rephrasing content unless required for a correction
- Compressing or summarizing in a way that drops information
- Reorganizing structure if it risks losing details

Preservation has higher priority than conciseness.

## **3. What to Include in Task Guidance:**
Store and maintain general knowledge that will be helpful for future tasks:
    - Repository Structure
        - Note: If you've only explored a portion of the codebase, clearly note this limitation in the repository structure guidance
    - Common commands (build, lint, test, pre-commit, etc.)
    - Code style preferences
    - Workflows and best practices
    - Any other repository-specific knowledge you learn
**IMPORTANT:**
    - Your task is to summarize a guidance snippet with ONLY valuable information based on the given coding agent trajectory, but NOT to continue the task.
    - ONLY EXTRACT valuable information that would be helpful for different future tasks, for example, how to configure the settings, how to setup the repository.
    - Do NOT include issue-specific information: e.g., what specific error you have ran into and how you fix it; implementation details or specific commands, code snippets, errors or failures; step-by-step procedures; technology-specific solutions; lengthy explanations or multiple sub-points; problem-specific fixes or error handling; etc.
    - The generated guidance snippet should be concise and well-organized. 
        - Group related information together under appropriate sections or headings.
        - Your generated task guidance snippet will be placed under the "## Task Guidance" section, so your highest level should start from "###".

## **4. Quality Standards:**
High-quality guidance is:
    - **Strategic but not tactical:** Focuses on 'how to think' rather than 'what to do'
    - **Universal:** Applies broadly to the problem class, not just this specific case
    - **Concise:** Each principle captures one essential insight
    - **Actionable:** Provides clear direction for future problem-solving
    - **Imperative:** Uses direct, commanding language

## **5. What Qualifies as an Update**

### A. Additions (allowed)
Add information only if it is:
- Not already present
- Generalizable across tasks
- Repository-level or workflow-level (not issue-specific)

### B. Corrections (allowed)
Modify existing content ONLY when:
- It is incorrect, misleading, or contradicted by stronger evidence
- You minimally edit the original statement to fix it
- You DO NOT delete the original idea unless it is fully invalid

### C. Non-qualifying (must ignore)
Do NOT include:
- Task-specific fixes, bugs, or errors
- One-off commands or debugging steps
- Implementation details or code snippets
- Step-by-step procedures
- Anything not reusable across future tasks

## **6. Requirements:**
- **Guidance Subject:** Use 'You' to address the coding agent directly
- **Guidance Size:** Maximum 512 tokens or less
- **Tense & Tone:** Use the present tense and imperative wording for guidance
- **Response Format:** Provide ONLY the guidance snippet in: <snippet>your generated guidance snippet</snippet>
""".strip()



SYSTEM_PROMPT_FOR_SINGLE_EPISODE = """
You are a helpful assistant who summarizes valuable information from coding agent trajectories to create concise high-level task guidance snippets.

## **1. Your Task:**
Analyze the given coding agent's trajectory and summarize a task guidance snippet comprising a list of valuable information to help the coding agent effectively solve future tasks.

## **2. What to Include:**
Store and maintain general knowledge that will be helpful for future tasks:
    - Repository Structure
        - Note: If you've only explored a portion of the codebase, clearly note this limitation in the repository structure guidance
    - Common commands (build, lint, test, pre-commit, etc.)
    - Code style preferences
    - Workflows and best practices
    - Any other repository-specific knowledge you learn
**IMPORTANT:**
    - Your task is to summarize a guidance snippet with ONLY valuable information based on the given coding agent trajectory, but NOT to continue the task.
    - ONLY EXTRACT valuable information that would be helpful for different future tasks, for example, how to configure the settings, how to setup the repository.
    - Do NOT include issue-specific information: e.g., what specific error you have ran into and how you fix it; implementation details or specific commands, code snippets, errors or failures; step-by-step procedures; technology-specific solutions; lengthy explanations or multiple sub-points; problem-specific fixes or error handling; etc.
    - The generated guidance snippet should be concise and well-organized. 
        - Group related information together under appropriate sections or headings.
        - Your generated task guidance snippet will be placed under the "## Task Guidance" section, so your highest level should start from "###".

## **3. Quality Standards:**
High-quality guidance is:
    - **Strategic but not tactical:** Focuses on 'how to think' rather than 'what to do'
    - **Universal:** Applies broadly to the problem class, not just this specific case
    - **Concise:** Each principle captures one essential insight
    - **Actionable:** Provides clear direction for future problem-solving
    - **Imperative:** Uses direct, commanding language

## **4. Requirements:**
- **Guidance Subject:** Use 'You' to address the coding agent directly
- **Guidance Size:** Maximum 512 tokens or less
- **Tense & Tone:** Use the present tense and imperative wording for guidance
- **Response Format:** Provide ONLY the guidance snippet in: <snippet>your generated guidance snippet</snippet>
""".strip()



WITH_REPO_DOT_MD = """
- **Compatibility:** Ensure your guidance snippet integrates nicely with existing knowledge in the following repo.md:
**Existing contents of `repo.md`:**
```markdown
This repository contains the code for OpenHands, an automated AI software engineer. It has a Python backend
(in the `openhands` directory) and React frontend (in the `frontend` directory).

## General Setup:
To set up the entire repo, including frontend and backend, run `make build`.
You don't need to do this unless the user asks you to, or if you're trying to run the entire application.

## Running OpenHands with OpenHands:
To run the full application to debug issues:
```bash
export INSTALL_DOCKER=0
export RUNTIME=local
make build && make run FRONTEND_PORT=12000 FRONTEND_HOST=0.0.0.0 BACKEND_HOST=0.0.0.0 &> /tmp/openhands-log.txt &
```

IMPORTANT: Before making any changes to the codebase, ALWAYS run `make install-pre-commit-hooks` to ensure pre-commit hooks are properly installed.

Before pushing any changes, you MUST ensure that any lint errors or simple test errors have been fixed.

* If you've made changes to the backend, you should run `pre-commit run --config ./dev_config/python/.pre-commit-config.yaml` (this will run on staged files).
* If you've made changes to the frontend, you should run `cd frontend && npm run lint:fix && npm run build ; cd ..`

The pre-commit hooks MUST pass successfully before pushing any changes to the repository. This is a mandatory requirement to maintain code quality and consistency.

If either command fails, it may have automatically fixed some issues. You should fix any issues that weren't automatically fixed,
then re-run the command to ensure it passes. Common issues include:
- Mypy type errors
- Ruff formatting issues
- Trailing whitespace
- Missing newlines at end of files

## Repository Structure
Backend:
- Located in the `openhands` directory
- Testing:
  - All tests are in `tests/unit/test_*.py`
  - To test new code, run `poetry run pytest tests/unit/test_xxx.py` where `xxx` is the appropriate file for the current functionality
  - Write all tests with pytest

Frontend:
- Located in the `frontend` directory
- Prerequisites: A recent version of NodeJS / NPM
- Setup: Run `npm install` in the frontend directory
- Testing:
  - Run tests: `npm run test`
  - To run specific tests: `npm run test -- -t "TestName"`
  - Our test framework is vitest
- Building:
  - Build for production: `npm run build`
- Environment Variables:
  - Set in `frontend/.env` or as environment variables
  - Available variables: VITE_BACKEND_HOST, VITE_USE_TLS, VITE_INSECURE_SKIP_VERIFY, VITE_FRONTEND_PORT
- Internationalization:
  - Generate i18n declaration file: `npm run make-i18n`
- Data Fetching & Cache Management:
  - We use TanStack Query (fka React Query) for data fetching and cache management
  - Data Access Layer: API client methods are located in `frontend/src/api` and should never be called directly from UI components - they must always be wrapped with TanStack Query
  - Custom hooks are located in `frontend/src/hooks/query/` and `frontend/src/hooks/mutation/`
  - Query hooks should follow the pattern use[Resource] (e.g., `useConversationMicroagents`)
  - Mutation hooks should follow the pattern use[Action] (e.g., `useDeleteConversation`)
  - Architecture rule: UI components → TanStack Query hooks → Data Access Layer (`frontend/src/api`) → API endpoints

## Template for Github Pull Request

If you are starting a pull request (PR), please follow the template in `.github/pull_request_template.md`.

## Implementation Details

These details may or may not be useful for your current task.

### Frontend

#### Action Handling:
- Actions are defined in `frontend/src/types/action-type.ts`
- The `HANDLED_ACTIONS` array in `frontend/src/state/chat-slice.ts` determines which actions are displayed as collapsible UI elements
- To add a new action type to the UI:
  1. Add the action type to the `HANDLED_ACTIONS` array
  2. Implement the action handling in `addAssistantAction` function in chat-slice.ts
  3. Add a translation key in the format `ACTION_MESSAGE$ACTION_NAME` to the i18n files
- Actions with `thought` property are displayed in the UI based on their action type:
  - Regular actions (like "run", "edit") display the thought as a separate message
  - Special actions (like "think") are displayed as collapsible elements only

#### Adding User Settings:
- To add a new user setting to OpenHands, follow these steps:
  1. Add the setting to the frontend:
     - Add the setting to the `Settings` type in `frontend/src/types/settings.ts`
     - Add the setting to the `ApiSettings` type in the same file
     - Add the setting with an appropriate default value to `DEFAULT_SETTINGS` in `frontend/src/services/settings.ts`
     - Update the `useSettings` hook in `frontend/src/hooks/query/use-settings.ts` to map the API response
     - Update the `useSaveSettings` hook in `frontend/src/hooks/mutation/use-save-settings.ts` to include the setting in API requests
     - Add UI components (like toggle switches) in the appropriate settings screen (e.g., `frontend/src/routes/app-settings.tsx`)
     - Add i18n translations for the setting name and any tooltips in `frontend/src/i18n/translation.json`
     - Add the translation key to `frontend/src/i18n/declaration.ts`
  2. Add the setting to the backend:
     - Add the setting to the `Settings` model in `openhands/storage/data_models/settings.py`
     - Update any relevant backend code to apply the setting (e.g., in session creation)

## Task Guidance
(Your generated task guidance snippet will be put here)
```
""".strip()
