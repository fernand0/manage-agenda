"""Workflows for evaluating configured LLM models."""

import time

from manage_agenda.config import config
from manage_agenda.llm import OllamaClient
from manage_agenda.sources import process_email_cli, process_txt_cli, process_web_cli


def evaluate_models(args, prompt=None, eval_type=None):
    """Evaluate available Ollama models against a prompt or source workflow."""
    results = []
    models = OllamaClient.list_models()
    if not models:
        print("No models available")
    for model_info in models:
        model_name = model_info["model"]
        print(f"Evaluating model: {model_name}")
        client = OllamaClient(model_name=model_name)

        if eval_type == "email":
            print(f"Cli (email): {process_email_cli(args, client)}")
        elif eval_type == "web":
            print(f"Cli (web): {process_web_cli(args, client)}")
        elif eval_type == "txt":
            print(f"Cli (txt): {process_txt_cli(args, client, source_name=config.MSG_TXT_DIR)}")
        elif prompt:
            print(f"Prompt: {prompt}")
            start_time = time.time()
            response = client.generate_text(prompt)
            duration = time.time() - start_time
            results.append({"model": model_name, "response": response, "duration": duration})

    if results:
        print("\n--- Evaluation Results ---")
        for result in results:
            print(f"Model: {result['model']}")
            print(f"Time taken: {result['duration']:.2f} seconds")
            print(f"Response: {result['response']}")
            print("--------------------")
