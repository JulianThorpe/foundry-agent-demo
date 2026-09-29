import json
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

ENDPOINT = "https://foundry-jt-demo.openai.azure.com/"
DEPLOYMENT = "gpt-5-mini"
MAX_ITERATIONS = 5

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21",
)

ALLOWED_PAGES = ["home", "pricing", "contact", "about"]

def navigate_to_page(page: str) -> dict:
    """Only allowlisted pages. A successful prompt injection can do nothing worse than open the wrong page."""
    if page not in ALLOWED_PAGES:
        return {"ok": False, "error": f"unknown page: {page}"}
    return {"ok": True, "page": page}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate_to_page",
            "description": "Take the visitor to a page on the site.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "enum": ALLOWED_PAGES}
                },
                "required": ["page"],
            },
        },
    }
]

def run(user_message: str) -> str:
    messages = [
        {"role": "system", "content": "You help visitors find the right page. Keep answers short."},
        {"role": "user", "content": user_message},
    ]
    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=DEPLOYMENT, messages=messages, tools=TOOLS
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content
        messages.append(message)
        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            result = navigate_to_page(**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })
    return "I could not complete that within the step limit."

if __name__ == "__main__":
    print(run("I want to know what this costs"))