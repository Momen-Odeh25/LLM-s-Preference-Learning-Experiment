LLM Preference Learning Experiment: Dynamic User and LLM-as-Judge Evaluation

1. Introduction

This report details the design, implementation, and evaluation methodology for an experiment aimed at assessing the ability of Large Language Models (LLMs) to learn and adapt to user preferences over the course of a conversation. The experiment introduces a novel approach by employing a dynamic, LLM-driven simulated user and an LLM-as-Judge for unbiased evaluation, enhancing the realism and robustness of the findings.

The primary objective is to compare two methods of providing conversational history to an LLM for preference learning: providing the full chat history versus providing a concise summary of the chat history. The ultimate goal is to determine which method leads to better adherence to user preferences in a follow-up interaction.


2. Experimental Design

The experiment is structured around 20 distinct topics, each with a predefined set of user preferences. Unlike traditional experiments with static user prompts, this design incorporates a dynamic, LLM-driven user to simulate more natural and adaptive human-AI interaction. Each topic undergoes a 10-turn interaction phase, followed by two independent test scenarios and a final LLM-as-Judge evaluation.

2.1. Topics and Preferences

Twenty diverse topics are loaded from a `topics\_data.json` file. Each topic is meticulously defined with:


`id`: A unique identifier for the topic.

`name`: A descriptive name for the topic (e.g., "Healthy Cooking Recipes").

`preferences`: A detailed dictionary outlining the simulated user's preferences for that specific topic. These preferences are categorized into:

`content`: Specifies a `focus` area (what the user likes to discuss) and `dislikes` (what the user wishes to avoid), along with a `dislikes\_statement` for natural language integration.

`stylistic`: Defines the preferred `tone` (e.g., "exciting, energetic tone", "formal and academic") and `format` (e.g., "short, punchy descriptions", "bullet points", "detailed explanations").


These preferences are designed to be specific, clear, and measurable, allowing for a robust evaluation of the LLM's ability to learn and adhere to them.


2.2. Dynamic LLM-Driven User

To simulate realistic user behavior, a dedicated LLM (`USER\_LLM\_MODEL`) acts as the simulated user. This `USER\_LLM\_MODEL` is distinct from the `TARGET\_LLM\_MODEL` (the LLM being evaluated) and the `SUMMARIZATION\_LLM\_MODEL` (used for generating summaries).

2.2.1. User LLM Initialization

At the beginning of each topic experiment, the `USER\_LLM\_MODEL` is initialized with a comprehensive system prompt. This prompt clearly defines its role as a human user, provides the specific topic, and outlines all the detailed preferences (content focus, dislikes, tone, and format) that it needs to convey, implicitly or explicitly, during the conversation. It is also informed about the initial prompt given to the `TARGET\_LLM\_MODEL` for context, but not to generate its own initial response.

2.2.2. Dynamic Turn Generation

Instead of fixed, pre-scripted user prompts for each turn, the `USER\_LLM\_MODEL` dynamically generates its responses. After each response from the `TARGET\_LLM\_MODEL`, the `USER\_LLM\_MODEL` receives this response and is prompted to generate a follow-up question or statement. This follow-up is designed to continue the conversation naturally while subtly or explicitly reinforcing the predefined user preferences. This approach ensures that the interaction feels more organic and allows for adaptive preference signaling based on the `TARGET\_LLM\_MODEL`'s previous output.

2.2.3. Parallel Conversation Management

The experiment maintains two parallel conversation histories:

`conversation\_history\_target\_llm`: This is the actual chat history between the `TARGET\_LLM\_MODEL` and the simulated user. This history is used to provide context to the `TARGET\_LLM\_MODEL` during the interaction turns and for the 'Full Chat History' test scenario.

`user\_llm\_conversation\_history`: This is the internal conversation history of the `USER\_LLM\_MODEL`. It helps the `USER\_LLM\_MODEL` maintain its own context, understand the flow of the conversation, and generate coherent and preference-aligned follow-up prompts. This history is crucial for the `USER\_LLM\_MODEL` to act as a consistent and intelligent simulated user.

Both histories are managed to ensure they stay within the context window limits of their respective LLMs, using a `manage\_context\_window` function that prunes older messages while preserving the system prompt.


2.3. Interaction Phase (10 Turns)

Each topic begins with an `initial\_user\_prompt` provided to the `TARGET\_LLM\_MODEL`. Following this, a 10-turn interaction phase unfolds. In each turn:

1\.  The `TARGET\_LLM\_MODEL` generates a response based on its current conversation history.

2\.  This response is then fed to the `USER\_LLM\_MODEL`.

3\.  The `USER\_LLM\_MODEL` generates the next user prompt, aiming to subtly or explicitly reinforce the predefined preferences for the topic.

4\.  This newly generated user prompt is added to the `TARGET\_LLM\_MODEL`'s conversation history, and the cycle continues.



This iterative process allows the `TARGET\_LLM\_MODEL` to receive continuous feedback and opportunities to learn the simulated user's preferences over time.

2.4. Final Follow-up Question Generation

After the 10 interaction turns are complete, the `USER\_LLM\_MODEL` is tasked with generating a single, concise final question. This question is specifically designed to test whether the `TARGET\_LLM\_MODEL` has successfully learned and incorporated the user's preferences throughout the conversation. The `USER\_LLM\_MODEL` is prompted to generate \*only\* the question, ensuring it is a direct and measurable test of preference adherence.


Test Scenarios

Upon completion of the interaction phase and the generation of the final follow-up question, two independent test scenarios are executed for each topic. The critical aspect here is that each scenario is run in a \*\*brand new, independent conversation\*\* with the `TARGET\_LLM\_MODEL` to eliminate any cross-contamination of context and ensure a fair comparison.



3.1. Scenario 1: Full Chat History Test

In this scenario, the `TARGET\_LLM\_MODEL` is presented with the entire conversation history from the 10 interaction turns, followed by the dynamically generated final follow-up question. The `messages` list for this API call is constructed as follows:

System Message: A system prompt instructing the LLM to act as a helpful assistant, use the provided history, and adhere to learned preferences.

Full Conversation History: All user and assistant turns from the interaction phase (`experiment\_record\["full\_chat\_history"]`).

Final User Message: The `follow\_up\_question` generated by the `USER\_LLM\_MODEL`.

The `TARGET\_LLM\_MODEL` then generates a response based on this complete context.


3.2. Scenario 2: Summarized Chat History Test

This scenario evaluates the `TARGET\_LLM\_MODEL`'s performance when provided with a concise summary of the conversation history instead of the full transcript. The summary is generated by a separate `SUMMARIZATION\_LLM\_MODEL` to ensure its independence from the `TARGET\_LLM\_MODEL`'s internal state.


3.2.1. Summary Generation

Before this test, the `SUMMARIZATION\_LLM\_MODEL` is given the full `experiment\_record\["full\_chat\_history"]` and prompted to summarize the user's preferences (content, tone, format, dislikes) from the conversation. This summary aims to distill the key preference signals into a compact form.


3.2.2. Summarized Test Prompt

Similar to Scenario 1, a new, independent conversation is initiated for this test. The `messages` list is constructed as follows:

System Message: A system prompt instructing the LLM to act as a helpful assistant, use the provided summary, and adhere to preferences described within it.

User Message: A single user message combining the generated summary and the final follow-up question. The structure is: "Based on the following summary of our conversation and my request:\\n\\nSummary of my preferences: {summary}\\n\\n{final\_follow\_up\_question}"


The `TARGET\_LLM\_MODEL` then generates a response based on this summarized context.


4. LLM-as-Judge Evaluation

To provide an objective and automated evaluation of which response better adheres to the user's preferences, an `LLM-as-Judge` approach is employed. This method replaces subjective human judgment or simplistic keyword matching with a more nuanced LLM-based assessment.


4.1. Judge LLM Initialization

A dedicated `JUDGE\_LLM\_MODEL` is used for this task. It is initialized with a system prompt that establishes its role as an impartial evaluator. This prompt explicitly provides the judge with the topic name and the precise user preferences (content focus, dislikes, tone, and format) for the current topic. Crucially, it is instructed to choose between Response A (Full History) and Response B (Summarized History) and to respond with \*only\* the letter 'A' or 'B', with no ties allowed.

4.2. Evaluation Process

After both `ai\_response\_full\_history` and `ai\_response\_summarized\_history` are generated, they are presented to the `JUDGE\_LLM\_MODEL`. To avoid bias, the responses are labeled generically as 'A' and 'B', without revealing which method generated them. The judge is also provided with the conversation summary, which can aid its understanding of the user's preferences.

4.3. Decision Parsing and Win Tracking

The output from the `JUDGE\_LLM\_MODEL` is programmatically parsed to extract either 'A' or 'B'. This decision is then mapped back to "Full History" or "Summarized History" to track wins. In cases where the judge LLM fails to provide a clear 'A' or 'B' response, or if one or both of the responses being judged were `None` (due to API errors), the outcome is recorded as a "Tie/Undecided" to ensure all topics are accounted for in the final win rate calculation.


5. Implementation Details

The experiment is implemented in Python, leveraging the `openai` library for LLM interactions. Key components include:

`get\_chat\_completion(messages, model, temperature)`: A robust function for making API calls to OpenAI models, including comprehensive error handling for API errors, connection errors, and rate limits.

`count\_tokens\_rough(text)`: A utility for roughly estimating token counts to manage context windows.

`manage\_context\_window(messages, max\_tokens)`: A function to trim conversation history to fit within the LLM's context limit, prioritizing recent messages and preserving the system prompt.

`summarize\_conversation(conversation\_history, model)`: Handles the generation of conversation summaries using a dedicated LLM.

`load\_topics\_data(file\_path)`: Loads the experiment topics and their preferences from a JSON file.

`llm\_as\_judge(response\_A, response\_B, topic\_data, conversation\_summary)`: The core function for the LLM-as-Judge evaluation.

`run\_experiment()`*: The main loop orchestrating the entire experiment, managing the interaction turns, executing test scenarios, and performing the final evaluation.


All experiment results, including the full chat history, generated summary, LLM responses for both scenarios, and the LLM judge's decision, are meticulously saved to a JSON file (`llm\_preference\_experiment\_results.json`) for later analysis. Final win rates for each scenario are calculated and printed to the console and is included at the end of this document.


6. Conclusion and Results

This experimental framework provides a robust and realistic methodology for evaluating LLM preference learning. By employing a dynamic, LLM-driven user and an LLM-as-Judge, it mitigates biases inherent in static prompts and manual evaluations, offering a more accurate assessment of an LLM's ability to adapt to user preferences over time and with varying context lengths.

--- Experiment Results ---

Number of experimented topics: 20

Conversation Turns per topic: 20 (10 turns for LLM, 10 turns for the simulated User)

Total Wins: {'Full History': 18, 'Summarized History': 2, 'Tie': 0}

Win Rate (Full History): 90.00%

Win Rate (Summarized History): 10.00%

