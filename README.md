LLM Preference Learning Experiment: Dynamic User and LLM-as-Judge Evaluation

Purpose – Compare two ways of giving an LLM its prior conversation when it tries to follow user preferences:

Full chat history versus 2. A compact summary of that history 

Topics & user profiles – 20 diverse topics are loaded from topics_data.json, each with granular content and style preferences so the model’s adherence can be measured objectively.

Dynamic simulated user – A separate USER_LLM (different from the target model) generates realistic follow-up prompts that keep signalling those preferences, while a SUMMARIZATION_LLM and a JUDGE_LLM play their own distinct roles.

Interaction phase – For each topic, the target model and the simulated user talk for 10 turns each (20 messages total). After that, the user-LLM asks one final question designed to reveal whether the model truly “got” the preferences.

Two test scenarios

Full-history test: the model gets the entire 10-turn transcript plus the final question.

Summarized-history test: the model instead receives a short summary of the same transcript plus the final question.

Automated judging – A neutral JUDGE_LLM sees both answers (labelled A/B), the explicit preference spec, and picks the one that better matches those preferences; no ties allowed. Its decision is parsed and counted.


--- Experiment Results ---

Number of experimented topics: 20

Conversation Turns per topic: 20 (10 turns for LLM, 10 turns for the simulated User)

Total Wins: {'Full History': 18, 'Summarized History': 2, 'Tie': 0}

Win Rate (Full History): 90.00%

Win Rate (Summarized History): 10.00%


