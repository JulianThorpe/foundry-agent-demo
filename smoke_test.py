from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

ENDPOINT = "https://foundry-jt-demo.openai.azure.com/"
DEPLOYMENT = "gpt-5-mini"

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21",
)

response = client.chat.completions.create(
    model=DEPLOYMENT,
    messages=[{"role": "user", "content": "Reply with exactly: connection works"}],
)

print(response.choices[0].message.content)
print("tokens:", response.usage.total_tokens)