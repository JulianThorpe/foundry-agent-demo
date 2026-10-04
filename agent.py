import json
import requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

ENDPOINT = "https://foundry-jt-demo.openai.azure.com/"
DEPLOYMENT = "gpt-5-mini"
MAX_ITERATIONS = 5
REQUEST_TIMEOUT_SECONDS = 5

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
    """Allowlisted pages only. A successful prompt injection can do nothing worse
    than open the wrong page."""
    if page not in ALLOWED_PAGES:
        return {"ok": False, "error": f"unknown page: {page}"}
    return {"ok": True, "page": page}


def get_current_temperature(latitude: float, longitude: float) -> dict:
    """Calls an external service. Every failure mode returns a structured result
    the model can reason about, rather than raising."""
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return {"ok": False, "error": "coordinates out of range"}
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"service unreachable: {type(exc).__name__}"}
    if response.status_code != 200:
        return {"ok": False, "error": f"service returned {response.status_code}"}
    try:
        celsius = response.json()["current"]["temperature_2m"]
    except (ValueError, KeyError, TypeError):
        return {"ok": False, "error": "unexpected response shape"}
    return {"ok": True, "celsius": celsius}


TOOL_FUNCTIONS = {
    "navigate_to_page": navigate_to_page,
    "get_current_temperature": get_current_temperature,
}


def execute_tool_call(name: str, arguments: str) -> dict:
    """Runs one tool call from the model. Anything the model gets wrong comes
    back as a structured failure instead of crashing the loop."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        args = json.loads(arguments)
    except json.JSONDecodeError:
        return {"ok": False, "error": "arguments were not valid JSON"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "arguments must be a JSON object"}
    try:
        return function(**args)
    except TypeError:
        return {"ok": False, "error": "wrong arguments for this tool"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate_to_page",
            "description": "Take the visitor to a page on the site.",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string", "enum": ALLOWED_PAGES}},
                "required": ["page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Current temperature in Celsius at a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
]


SYSTEM_PROMPT = (
    "You help visitors. You have exactly two abilities: opening one of these pages "
    "(home, pricing, contact, about) and looking up the current temperature at a "
    "location. You cannot give forecasts, wind, rain or any other weather detail. "
    "Do not offer anything outside these two abilities. If a tool reports a "
    "failure, tell the user plainly rather than inventing an answer."
    "If the user names a place, work out its coordinates yourself. If no place "
    "is given, ask which city they mean."
)


def run(messages: list) -> str:
    """Runs one turn of the conversation. Appends to `messages` in place, so the
    caller keeps the history between turns."""
    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=DEPLOYMENT, messages=messages, tools=TOOLS
        )
        message = response.choices[0].message
        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content})
            return message.content
        messages.append(message)
        for call in message.tool_calls:
            result = execute_tool_call(call.function.name, call.function.arguments)
            print(f"  [tool] {call.function.name}({call.function.arguments}) -> {result}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )
    return "I could not complete that within the step limit."


if __name__ == "__main__":
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Ask something (blank line to quit).")
    while question := input("> ").strip():
        history.append({"role": "user", "content": question})
        print(run(history))
