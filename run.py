import openai
import json
import os
import time
import re

# Initialize the OpenAI client for API

OPENAI_API_KEY = "PLACE API KEY"
client = openai.OpenAI(api_key=OPENAI_API_KEY)

TARGET_LLM_MODEL = "gpt-4o-mini"
USER_LLM_MODEL = "gpt-4o-mini"
SUMMARIZATION_LLM_MODEL = "gpt-4o-mini"

NUM_INTERACTION_TURNS = 10 # 10 user turns, 10 LLM turns
MAX_TOKENS_PER_CONVERSATION = 8000 #
MAX_RESPONSE_TOKENS = 500 # Max tokens for each LLM response

# Path to the topics data JSON file
TOPICS_DATA_FILE = "topics_data.json"

def get_chat_completion(messages, model, temperature=0.7):
    """Sends messages to the ChatGPT API and returns the assistant\'s response."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=MAX_RESPONSE_TOKENS,
        )
        return response.choices[0].message.content
    except openai.APIError as e:
        print(f"OpenAI API returned an API Error: {e}")
        return None
    except openai.APIConnectionError as e:
        print(f"Failed to connect to OpenAI API: {e}")
        return None
    except openai.RateLimitError as e:
        print(f"OpenAI API request exceeded rate limit: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during API call: {e}")
        return None

def count_tokens_rough(text):
    """Roughly counts tokens (approx. 1 token per 4 characters for English)."""
    if text is None:
        return 0
    return len(text) / 4

def manage_context_window(messages, max_tokens):
    """Trims the message history to fit within the max_tokens limit.
    Keeps the system message and recent messages.
    """
    if not messages:
        return []

    # Assuming the first message is always the system message and should be kept
    system_message = messages[0] if messages and messages[0]["role"] == "system" else None
    conversation_messages = messages[1:] if system_message else messages

    current_tokens = (count_tokens_rough(system_message["content"]) if system_message else 0) + \
                     sum(count_tokens_rough(m["content"]) for m in conversation_messages)

    # Remove oldest messages until within limit, but keep at least the system message
    while current_tokens > max_tokens and len(conversation_messages) > 0:
        removed_message = conversation_messages.pop(0)
        current_tokens -= count_tokens_rough(removed_message["content"])

    return ([system_message] if system_message else []) + conversation_messages

def summarize_conversation(conversation_history, model=SUMMARIZATION_LLM_MODEL):
    """Summarizes the conversation history, focusing on user preferences.
    Uses a separate LLM call (simulating a new chat thread)."""
    summarization_prompt = "Summarize the user\'s preferences (content, tone, format, dislikes) from the following conversation. Be concise and capture all key preferences:"
    
    # Format history for summarization LLM
    formatted_history = "\n".join([f"{m["role"]}: {m["content"]}" for m in conversation_history])

    summarization_messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes user preferences from conversations."},
        {"role": "user", "content": summarization_prompt + "\n\n" + formatted_history}
    ]
    
    summary = get_chat_completion(summarization_messages, model=model, temperature=0.2) # Lower temperature for factual summary
    return summary

def load_topics_data(file_path):
    """Loads topics data from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            topics_data = json.load(f)
        print(f"Successfully loaded {len(topics_data)} topics from {file_path}")
        return topics_data
    except FileNotFoundError:
        print(f"Error: Topics data file not found at {file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in topics data file: {e}")
        return []
    except Exception as e:
        print(f"Error loading topics data: {e}")
        return []

def user_llm_as_judge(response_A, response_B, topic_data, user_llm_conversation_history):
    """Uses the USER LLM to judge which response (A or B) better adheres to user preferences.
    The judge LLM is given the topic preferences and its own conversation history.
    """
    preferences = topic_data["preferences"]
    topic_name = topic_data["name"]

    # The system prompt for the USER LLM when it acts as a judge
    judge_system_prompt = (
        f"You are simulating a human user. You have just completed a conversation with an AI assistant about {topic_name}.\n"
        f"Your preferences for this conversation were:\n"
        f"- Content Focus: {preferences["content"]["focus"]}\n"
        f"- Content Dislikes: {preferences["content"]["dislikes_statement"]}\n"
        f"- Tone: {preferences["stylistic"]["tone"]}\n"
        f"- Format: {preferences["stylistic"]["format"]}\n\n"
        f"You will now be presented with two responses (labeled A and B) to your final question. Your task is to choose which response, A or B, better adheres to ALL of your stated preferences and the preferences you conveyed throughout the conversation.\n"
        f"You MUST choose one; no ties are allowed. Respond with ONLY the letter \'A\' or \'B\'. Do NOT include any other text or explanation."
    )

    # The user prompt for the USER LLM when it acts as a judge
    judge_user_prompt = (
        f"Here are the two responses to your final question:\n\n"
        f"Response A:\n{response_A}\n\n"
        f"Response B:\n{response_B}\n\n"
        f"Which response (A or B) better adheres to your preferences? Respond with ONLY \'A\' or \'B\'."
    )

    # Use the USER LLM's existing conversation history, append the judging task
    # We create a new list to avoid modifying the original user_llm_conversation_history
    judge_messages = list(user_llm_conversation_history)
    # Replace the system message with the judge-specific system prompt
    judge_messages[0] = {"role": "system", "content": judge_system_prompt}
    judge_messages.append({"role": "user", "content": judge_user_prompt})

    judge_decision = get_chat_completion(judge_messages, model=USER_LLM_MODEL, temperature=0.1) # Low temperature for decisive answer
    
    if judge_decision:
        # Use regex to find A or B case-insensitively
        match = re.search(r'[ABab]', judge_decision)
        if match:
            return match.group(0).upper()
    return None

# Main Experiment

def run_experiment():
    """Main function to run the experiment."""
    
    # Load topics data from JSON file
    topics_data = load_topics_data(TOPICS_DATA_FILE)
    if not topics_data:
        print("No topics data loaded. Exiting.")
        return None, None

    all_experiment_results = []
    wins = {"Full History": 0, "Summarized History": 0, "Tie": 0}

    for topic_data in topics_data:
        print(f"\n--- Running Experiment for Topic: {topic_data["name"]} ---")
        experiment_record = {
            "topic_id": topic_data["id"],
            "topic_name": topic_data["name"],
            "preferences": topic_data["preferences"],
            "initial_user_prompt": topic_data["initial_user_prompt"],
            "full_chat_history": [],
            "summarization_prompt": "Summarize the user\'s preferences (content, tone, format, dislikes) from the following conversation. Be concise and capture all key preferences:",
            "generated_summary": None,
            "follow_up_question": None, # Will be generated by USER LLM
            "ai_response_full_history": None,
            "ai_response_summarized_history": None,
            "llm_judge_decision": None
        }

        # Initialize conversation history for the TARGET LLM
        conversation_history_target_llm = [
            {"role": "system", "content": f"You are a helpful AI assistant specializing in {topic_data["name"]}. You learn user preferences over time. The user prefers {topic_data["preferences"]["content"]["focus"]}, dislikes {topic_data["preferences"]["content"]["dislikes_statement"]}, and likes a {topic_data["preferences"]["stylistic"]["tone"]} and {topic_data["preferences"]["stylistic"]["format"]} approach."}
        ]

        # Initialize conversation history for the USER LLM
        user_llm_conversation_history = [
            {"role": "system", "content": (
                f"You are simulating a human user interacting with an AI assistant about {topic_data["name"]}.\n"
                f"Your goal is to guide the conversation to reveal your preferences, and then ask a final question that tests if the AI learned them.\n"
                f"Your preferences are:\n"
                f"- Content Focus: {topic_data["preferences"]["content"]["focus"]}\n"
                f"- Content Dislikes: {topic_data["preferences"]["content"]["dislikes_statement"]}\n"
                f"- Tone: {topic_data["preferences"]["stylistic"]["tone"]}\n"
                f"- Format: {topic_data["preferences"]["stylistic"]["format"]}\n\n"
                f"For each turn, you will receive the AI\'s previous response. Your task is to generate a follow-up question or statement that continues the conversation and subtly (or explicitly) reinforces your preferences. Make your responses sound natural and human-like.\n"
                f"The initial prompt you gave the AI was: \'{topic_data["initial_user_prompt"]}\'\n"
                f"When asked for the final question, generate a single question that specifically tests the AI\'s understanding of your preferences. Do NOT include any other text in your final question response."
            )}
        ]
        # Add the initial user prompt to the target LLM\'s history
        initial_user_prompt = topic_data["initial_user_prompt"]
        conversation_history_target_llm.append({"role": "user", "content": initial_user_prompt})
        experiment_record["full_chat_history"].append({"role": "user", "content": initial_user_prompt})

        # Simulate 10 turns of interaction
        successful_turns = 0
        for turn in range(1, NUM_INTERACTION_TURNS + 1):
            print(f"Turn {turn} - Generating LLM response...")
            # LLM responds to the user\'s last prompt
            managed_history_target = manage_context_window(conversation_history_target_llm, MAX_TOKENS_PER_CONVERSATION)
            llm_response = get_chat_completion(managed_history_target, TARGET_LLM_MODEL)
            
            if llm_response:
                conversation_history_target_llm.append({"role": "assistant", "content": llm_response})
                experiment_record["full_chat_history"].append({"role": "assistant", "content": llm_response})
                print(f"Turn {turn} - LLM: {llm_response[:50]}...")
                successful_turns += 1

                # USER LLM generates next prompt based on LLM\'s response
                user_llm_conversation_history.append({"role": "assistant", "content": llm_response}) # LLM\'s response is assistant to USER LLM
                user_llm_prompt_messages = list(user_llm_conversation_history) # Copy for this turn\'s prompt generation
                user_llm_prompt_messages.append({"role": "user", "content": "Generate your next turn as the user. Make it natural and incorporate preference feedback."})
                
                print(f"Turn {turn} - Generating USER prompt...")
                user_prompt_from_llm = get_chat_completion(user_llm_prompt_messages, USER_LLM_MODEL, temperature=0.8) # Higher temp for creativity
                
                if user_prompt_from_llm:
                    conversation_history_target_llm.append({"role": "user", "content": user_prompt_from_llm})
                    experiment_record["full_chat_history"].append({"role": "user", "content": user_prompt_from_llm})
                    user_llm_conversation_history.append({"role": "user", "content": user_prompt_from_llm}) # User\'s prompt is user to USER LLM
                    print(f"Turn {turn} - USER: {user_prompt_from_llm[:50]}...")
                else:
                    print(f"Turn {turn} - USER LLM failed to generate prompt. Using generic fallback.")
                    fallback_prompt = f"Continuing our discussion on {topic_data["name"]}. What else can you add?"
                    conversation_history_target_llm.append({"role": "user", "content": fallback_prompt})
                    experiment_record["full_chat_history"].append({"role": "user", "content": fallback_prompt})
                    user_llm_conversation_history.append({"role": "user", "content": fallback_prompt})
            else:
                print(f"Turn {turn} - TARGET LLM response failed. Skipping user prompt generation for this turn.")
                # If TARGET LLM fails, we can\'t generate a user prompt based on its response
            time.sleep(1) # To avoid hitting rate limits

        if successful_turns == 0:
            print(f"All TARGET LLM turns failed for topic {topic_data["name"]}. Skipping this topic.")
            continue

        # USER LLM generates FINAL follow-up question
        print("\n--- USER LLM generating final follow-up question ---")
        final_question_messages = list(user_llm_conversation_history) # Use the USER LLM's full history
        final_question_messages.append({"role": "user", "content": "Now, generate a single, concise final question that specifically tests the AI\'s understanding of your preferences based on our conversation. Respond with ONLY the question."})
        
        final_follow_up_question = get_chat_completion(final_question_messages, USER_LLM_MODEL, temperature=0.5)
        experiment_record["follow_up_question"] = final_follow_up_question
        if final_follow_up_question:
            print(f"Final Follow-up Question: {final_follow_up_question[:100]}...")
        else:
            print("Final Follow-up Question: Failed to generate. Skipping topic.")
            continue

        # Scenario 1: Full Chat History Test (New Conversation)
        print("\n--- Running Scenario 1: Full Chat History (New Conversation) ---")
        full_history_test_messages = [
            {"role": "system", "content": f"You are a helpful AI assistant specializing in {topic_data["name"]}. You will be provided with a conversation history and a follow-up question. Your task is to answer the follow-up question based on the provided history, adhering to the user\'s preferences as learned from the conversation."}
        ]
        full_history_test_messages.extend(experiment_record["full_chat_history"])
        full_history_test_messages.append({"role": "user", "content": final_follow_up_question})
        
        full_history_test_messages = manage_context_window(full_history_test_messages, MAX_TOKENS_PER_CONVERSATION)

        ai_response_full = get_chat_completion(full_history_test_messages, TARGET_LLM_MODEL)
        experiment_record["ai_response_full_history"] = ai_response_full
        if ai_response_full:
            print(f"Full History Response: {ai_response_full[:100]}...")
        else:
            print("Full History Response: Failed")

        # Scenario 2: Summarized Chat History Test (New Conversation)
        print("\n--- Running Scenario 2: Summarized Chat History (New Conversation) ---")
        summary = summarize_conversation(experiment_record["full_chat_history"], SUMMARIZATION_LLM_MODEL)
        experiment_record["generated_summary"] = summary
        if summary:
            print(f"Generated Summary: {summary[:100]}...")
        else:
            print("Generated Summary: Failed")

        summarized_history_test_messages = [
            {"role": "system", "content": f"You are a helpful AI assistant specializing in {topic_data["name"]}. You will be provided with a summary of a conversation and a follow-up question. Your task is to answer the follow-up question based on the provided summary, adhering to the user\'s preferences as described in the summary."},
            {"role": "user", "content": f"Based on the following summary of our conversation and my request:\n\nSummary of my preferences: {summary}\n\n{final_follow_up_question}"}
        ]
        
        ai_response_summarized = get_chat_completion(summarized_history_test_messages, TARGET_LLM_MODEL)
        experiment_record["ai_response_summarized_history"] = ai_response_summarized
        if ai_response_summarized:
            print(f"Summarized History Response: {ai_response_summarized[:100]}...")
        else:
            print("Summarized History Response: Failed")

        # USER LLM as Judge Evaluation
        print("\n--- USER LLM as Judge Evaluation ---")
        if ai_response_full and ai_response_summarized:
            judge_result = user_llm_as_judge(ai_response_full, ai_response_summarized, topic_data, user_llm_conversation_history)
            if judge_result == 'A':
                experiment_record["llm_judge_decision"] = "Full History"
                wins["Full History"] += 1
            elif judge_result == 'B':
                experiment_record["llm_judge_decision"] = "Summarized History"
                wins["Summarized History"] += 1
            else:
                experiment_record["llm_judge_decision"] = "NAN"
                wins["Tie"] += 1 # Count as tie if judge fails to give A or B
            print(f"LLM Judge Decision: {experiment_record["llm_judge_decision"]}")
        else:
            print("Skipping judge evaluation due to failed responses.")
            experiment_record["llm_judge_decision"] = "Skipped (Responses Failed)"
            wins["Tie"] += 1 # Count as tie if responses failed

        all_experiment_results.append(experiment_record)
        time.sleep(2) # Pause between topics

    # Final Results
    print("\n--- Experiment Complete ---")
    print("Total Wins:", wins)

    total_topics = len([r for r in all_experiment_results if r["llm_judge_decision"] is not None and r["llm_judge_decision"] != "Skipped (Responses Failed)"])
    if total_topics > 0:
        win_rate_full = (wins["Full History"] / total_topics) * 100
        win_rate_summarized = (wins["Summarized History"] / total_topics) * 100
        tie_rate = (wins["Tie"] / total_topics) * 100

        print(f"Win Rate (Full History): {win_rate_full:.2f}%")
        print(f"Win Rate (Summarized History): {win_rate_summarized:.2f}%")
        print(f"Tie Rate: {tie_rate:.2f}%")
    else:
        print("No successful experiments to calculate win rates.")

    # Save Results
    output_filename = "llm_preference_experiment_results.json"
    with open(output_filename, "w") as f:
        json.dump(all_experiment_results, f, indent=4)
    print(f"All experiment results saved to {output_filename}")

    return all_experiment_results, wins

if __name__ == "__main__":
    # Run the experiment

    results, win_counts = run_experiment()
