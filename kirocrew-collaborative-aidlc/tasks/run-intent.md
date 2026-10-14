# Run a Collaborative AI-DLC intent through KiroCrew

1. Load the `collaborative-aidlc-kirocrew` skill.
2. Bind execution to the target repository and initialize the supplied intent.
3. Read the file-native workflow state before every dispatch.
4. Dispatch only the current stage to its named specialist agent.
5. Collect support-agent contributions and integrate them into declared artifacts.
6. Run deterministic checks and the repository's relevant tests.
7. Dispatch the declared clean-room reviewer when present.
8. Present the stage evidence and findings to the human.
9. Persist only the human's explicit gate decision.
10. Continue until the next gate or until the intent is complete.

Do not deploy infrastructure, push branches, merge changes, or open a pull request unless separately requested.
