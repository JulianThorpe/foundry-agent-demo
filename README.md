# Bounded agent on Microsoft Foundry

A small tool-using agent running on a Microsoft Foundry model deployment, written to
compare the managed-platform experience against building the same thing directly on a
model vendor's API.

The agent itself is deliberately small: two narrowly scoped tools, a capped reasoning
loop, and a test suite that targets the boundaries rather than the model. The
interesting part is the reasoning behind each of those choices, and what the platform
does and does not do for you.

## Design decisions

**A navigation tool with an allowlist.** The agent can send a visitor to a page, but
only to a page on a fixed list. An agent's risk is a function of what its tools permit,
so the worst outcome of a successful prompt injection here is an unwanted page change.
Widening that surface should be a deliberate decision, not a default.

**A second tool that can fail.** The temperature lookup calls an external weather
service (Open-Meteo), so it can time out, return a server error, or send back something
unexpected. None of those raise an exception. Each comes back to the model as a
structured result (`{"ok": false, "error": ...}`), and the system prompt tells the model
to report the failure plainly rather than invent an answer. Coordinates are validated
before any network call is made.

**The model's mistakes are contained too.** Tool calls pass through a single dispatcher
that rejects unknown tool names, malformed JSON and wrong argument names with the same
structured failure. A bad call from the model costs one loop iteration, not the whole
run.

**A capped loop.** An agent loop is unbounded unless you bound it. The iteration cap is
five, with a plain fallback message when it is reached, so a confused model costs a
fixed number of calls rather than an open-ended bill.

**Tests target the boundaries, not the model.** Model output is non-deterministic, so
testing it mostly tests chance. The boundaries are deterministic and they are what
matters for safety, so the 13 tests cover three areas: the page allowlist, every failure
path of the external call (bad coordinates, timeout, server error, malformed response),
and the dispatcher's handling of bad calls from the model. The network is mocked
throughout, so the suite runs in CI with no Azure credentials and no outbound requests.

**No API keys.** Authentication uses `DefaultAzureCredential` and a bearer token
provider, so access is granted by role assignment rather than by a secret in a config
file. This is the model Foundry pushes you toward and it is a real difference from
key-based vendor APIs.

## What this is not

Small scale, two tools, no retrieval, no production traffic. An embedding model is
deployed alongside the chat model but is not yet used. This is a study artefact rather
than a product.

## Running it

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
az login --tenant <your-tenant-id>
python agent.py
pytest -v
```

`python agent.py` starts an interactive chat. Each tool call is printed as it happens,
so you can see what the agent actually did before its answer. A blank line quits.
Useful things to try: a temperature question for any city, a request for an allowed
page, a request for a page that is not on the allowlist, and a question with no
location given.

The caller needs the `Cognitive Services OpenAI User` role on the resource group.
Subscription Owner is not sufficient, because the built-in Owner role carries no data
actions. This produces a 401 that looks exactly like a code fault.

Sign in with `az login --tenant`, not `--use-device-code`. Device-code sign-in is
blocked by Microsoft Entra security defaults on a new tenant, and an account that is
a guest in other directories may hit Conditional Access policies there too. The
resulting errors (AADSTS530035, AADSTS530036) mention every tenant the account
belongs to, which makes them look more serious than they are.

## Provisioning

Everything was provisioned from the CLI rather than the portal, so it is reproducible:

```
az group create --name rg-foundry-demo --location australiaeast
az provider register --namespace Microsoft.CognitiveServices --wait
az cognitiveservices account create --name foundry-jt-demo --resource-group rg-foundry-demo \
  --location australiaeast --kind AIServices --sku S0 --custom-domain foundry-jt-demo --yes
az cognitiveservices account deployment create --name foundry-jt-demo \
  --resource-group rg-foundry-demo --deployment-name gpt-5-mini \
  --model-name gpt-5-mini --model-version "2025-08-07" \
  --model-format OpenAI --sku-capacity 10 --sku-name GlobalStandard
az role assignment create --assignee <object-id> \
  --role "Cognitive Services OpenAI User" --scope <resource-group-id>
```

## Notes from building it

Things that a tutorial does not tell you and a working session does:

**Resource providers are opt-in.** A new subscription is not registered for
`Microsoft.CognitiveServices` until you register it, and the failure reads as a
permissions problem rather than a configuration one.

**Catalogue availability, regional capacity and subscription quota are three different
things.** A model can be listed, be available in your region, and still have a quota
limit of zero for your subscription. The first model chosen deployed nowhere; checking
quota first would have been quicker than reading the error.

**Model versions have a lifecycle.** Deployments pin a dated version, versions enter a
deprecating state and stop accepting new deployments, and the default upgrade behaviour
moves you forward when a new default appears. Somebody has to own that. Calling a vendor
API directly has the same underlying problem but hides it behind a model alias.

**A content filter policy is applied by default.** The deployment came with one attached
without being asked for. That is a sensible default and it is also a behaviour you
inherit rather than choose, which is worth knowing before an assurance conversation.

## The comparison

Building the same shape of agent against a vendor API directly means owning more and
inheriting less: you choose the model and the safety layer, and you carry the
configuration. On Foundry, the deployment is a managed resource with quota, versioning,
content filtering and identity-based access attached to it, which removes work and adds
governance surface at the same time.

Neither is better in the abstract. The question is which set of defaults you want to
inherit and which decisions you want to keep, and that is a judgement that should be
made before the build rather than discovered during it.
