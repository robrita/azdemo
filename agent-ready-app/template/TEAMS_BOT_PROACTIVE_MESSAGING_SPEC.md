# Teams Bot with Proactive Messaging — Technical Specification

> Portable spec for building a Microsoft Teams chatbot that supports both interactive conversations and proactive notifications to all users. Export this to any Python project.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Azure Resources Required](#azure-resources-required)
4. [App Registration Setup](#app-registration-setup)
5. [Bot Capabilities](#bot-capabilities)
6. [Proactive Messaging — How It Works](#proactive-messaging--how-it-works)
7. [Storing Conversation References](#storing-conversation-references)
8. [Sending Without Stored References](#sending-without-stored-references)
9. [Getting User Entra Object IDs](#getting-user-entra-object-ids)
10. [Proactive App Installation via Graph](#proactive-app-installation-via-graph)
11. [Python Sample Code](#python-sample-code)
12. [API Endpoints](#api-endpoints)
13. [Graph API Permissions Summary](#graph-api-permissions-summary)
14. [Best Practices](#best-practices)
15. [Key Microsoft Docs References](#key-microsoft-docs-references)

---

## Overview

A Teams bot that:

- **Conversational**: Users can chat with the bot 1:1 — ask questions, run commands, receive responses.
- **Proactive notifications**: The bot can push messages to all users who have the app installed, without the user initiating a conversation first.

### Key Terms

| Term | Definition |
|---|---|
| **Proactive message** | A message sent by a bot NOT in response to a user request. |
| **ConversationReference** | A serializable object containing everything needed to resume a conversation (`user.id`, `conversation.id`, `serviceUrl`, `bot.id`, `tenantId`). |
| **aadObjectId** | A user's Microsoft Entra ID (Azure AD) Object ID. Globally unique per user. |
| **Bot Connector API** | REST API used by bots to send/receive messages to/from channels (Teams). |
| **Microsoft Graph API** | REST API for interacting with Microsoft 365 services (users, Teams, apps). |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Microsoft Teams                        │
│                                                          │
│  User ←→ Bot (chat)                                      │
│  User ←── Bot (proactive notification)                   │
└─────────────────────┬────────────────────────────────────┘
                      │ HTTPS
                      ▼
┌──────────────────────────────────────────────────────────┐
│              Your Bot Application                         │
│                                                          │
│  POST /api/messages     ── handles incoming chat          │
│  POST /api/notify       ── triggers proactive broadcast   │
│                                                          │
│  ┌─────────────────┐    ┌──────────────────────┐         │
│  │  Bot Handler     │    │  Notification Service │         │
│  │  (on_message,    │    │  (iterate refs,       │         │
│  │   on_members_    │    │   continue_convo)     │         │
│  │   added)         │    │                       │         │
│  └────────┬─────────┘    └──────────┬────────────┘         │
│           │                          │                     │
│           ▼                          ▼                     │
│  ┌──────────────────────────────────────────────┐         │
│  │  Conversation Reference Store (DB)            │         │
│  │  key: user_aad_object_id                      │         │
│  │  value: ConversationReference (JSON)          │         │
│  └──────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│  External Services                                        │
│                                                          │
│  • Azure Bot Service (bot registration + channel routing) │
│  • Microsoft Graph API (user lookup, app install)         │
│  • Microsoft Entra ID (authentication, tokens)            │
└──────────────────────────────────────────────────────────┘
```

---

## Azure Resources Required

| Resource | Purpose |
|---|---|
| **Azure Bot Service** (or Azure AI Bot Service) | Bot registration; routes messages between Teams and your backend |
| **App Registration (Microsoft Entra ID)** | Provides App ID + Secret for bot authentication and Graph API calls |
| **App Service / Azure Functions / Container** | Hosts your bot backend code |
| **Database** (CosmosDB, PostgreSQL, etc.) | Persists conversation references |

---

## App Registration Setup

1. **Azure Portal** → **App registrations** → **New registration**
2. Set **Supported account types** to "Accounts in any organizational directory" (multitenant) or single-tenant as needed
3. Note the **Application (client) ID** — this is your `BOT_APP_ID`
4. **Certificates & secrets** → **New client secret** → note the value as `BOT_APP_PASSWORD`
5. **API permissions** → Add:
   - `User.Read.All` (Application) — to list users
   - `TeamsAppInstallation.ReadWriteSelfForUser.All` (Application) — to install app for users
6. **Grant admin consent** for the above permissions
7. **Azure Bot Service** → Create a bot resource → set Messaging endpoint to `https://your-domain/api/messages`
8. **Channels** → Add Microsoft Teams channel

---

## Bot Capabilities

### Conversational (Reactive)

Users message the bot → bot processes → bot replies.

- Scopes: **Personal** (1:1), **Group Chat**, **Channel** (requires @mention)
- Handled via `on_message_activity` in the bot handler
- Supports: text, Adaptive Cards, file attachments

### Proactive Notifications

Bot initiates a message → delivered to user without prior interaction.

- Requires a stored `ConversationReference` OR the user's `aadObjectId`
- Bot must be installed for the target user
- Uses `adapter.continue_conversation()` (SDK) or Bot Connector REST API

---

## Proactive Messaging — How It Works

### The 3-Step Pattern

```
1. CAPTURE  →  On app install / user message, extract ConversationReference
2. STORE    →  Persist to database (keyed by user's aadObjectId)
3. SEND     →  When triggered, iterate stored references → continue_conversation()
```

### Detailed Flow

1. User installs the bot → bot receives `conversationUpdate` activity with `membersAdded`
2. Bot extracts `ConversationReference` from the activity:
   ```python
   conversation_reference = TurnContext.get_conversation_reference(activity)
   ```
3. Bot stores `conversation_reference` in a database, keyed by `user.aadObjectId` or `user.id`
4. When a notification is needed (admin action, scheduled job, external trigger):
   - Retrieve all stored conversation references from DB
   - For each reference, call `adapter.continue_conversation(reference, callback, app_id)`
   - In the callback, send the message via `turn_context.send_activity()`

### Important Constraints

- **Bot must be installed** for the user (personal scope) before sending proactive messages
- Sending to a user without the app installed returns `403 ForbiddenOperationException`
- **Service URL can change** over time — re-acquire if calls start failing
- **Throttling**: Teams limits message rate; use controlled concurrency for bulk sends
- **403 with `MessageWritesBlocked`**: User blocked or uninstalled the bot

---

## Storing Conversation References

### Data Model

```python
# What to store per user
{
    "user_aad_object_id": "87d349ed-44d7-43e1-9a83-5f2406dee5bd",
    "user_name": "John Doe",
    "conversation_reference": {
        "activityId": "f:abc123",
        "user": {"id": "29:1abc...", "name": "John Doe", "aadObjectId": "87d349ed-..."},
        "bot": {"id": "28:bot-app-id", "name": "MyBot"},
        "conversation": {"id": "a:1xyz...", "tenantId": "tenant-id"},
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/"
    },
    "stored_at": "2026-03-17T10:00:00Z"
}
```

### When to Capture

| Event | Handler | Action |
|---|---|---|
| App installed | `on_members_added_activity` | Store reference + send welcome message |
| User sends any message | `on_message_activity` | Update reference (keeps serviceUrl fresh) |
| App uninstalled | `on_members_removed_activity` | Remove reference |

### Python: Capture Logic

```python
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity, ConversationReference


class ProactiveBot(ActivityHandler):
    def __init__(self, db):
        self.db = db  # Your database client

    def _save_conversation_reference(self, activity: Activity):
        ref = TurnContext.get_conversation_reference(activity)
        user_aad_id = activity.from_property.aad_object_id or ref.user.id
        self.db.upsert_conversation_reference(user_aad_id, ref.serialize())

    async def on_conversation_update_activity(self, turn_context: TurnContext):
        self._save_conversation_reference(turn_context.activity)
        return await super().on_conversation_update_activity(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        self._save_conversation_reference(turn_context.activity)
        # ... handle user message ...

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Welcome! I'll send you notifications.")

    async def on_members_removed_activity(self, members_removed, turn_context: TurnContext):
        for member in members_removed:
            self.db.remove_conversation_reference(member.aad_object_id or member.id)
```

---

## Sending Without Stored References

If you don't have conversation references (e.g., existing app but never stored them), there are two approaches:

### Approach A: Bot Connector REST API — Create Conversation from aadObjectId

No stored reference needed. Requires only the user's Entra Object ID.

```python
import aiohttp

SERVICE_URL = "https://smba.trafficmanager.net/teams/"


async def get_bot_token(app_id: str, app_password: str) -> str:
    url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_password,
            "scope": "https://api.botframework.com/.default",
        }) as resp:
            return (await resp.json())["access_token"]


async def send_proactive_to_user(
    app_id: str, app_password: str, tenant_id: str,
    user_aad_object_id: str, message_text: str,
):
    token = await get_bot_token(app_id, app_password)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Step 1: Create 1:1 conversation
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVICE_URL}v3/conversations", headers=headers, json={
            "bot": {"id": app_id},
            "members": [{"id": user_aad_object_id}],
            "channelData": {"tenant": {"id": tenant_id}},
            "isGroup": False,
        }) as resp:
            conversation_id = (await resp.json())["id"]

        # Step 2: Send message
        async with session.post(
            f"{SERVICE_URL}v3/conversations/{conversation_id}/activities",
            headers=headers,
            json={"type": "message", "text": message_text},
        ) as resp:
            return await resp.json()
```

### Approach B: Microsoft Graph API — Recover Chat IDs from Existing Installs

For users who already have the app installed but you lost the reference.

```python
async def get_chat_id_for_user(graph_token: str, user_id: str, teams_app_id: str) -> str | None:
    headers = {"Authorization": f"Bearer {graph_token}"}
    async with aiohttp.ClientSession() as session:
        # Find installation
        url = (
            f"https://graph.microsoft.com/v1.0/users/{user_id}/teamwork/installedApps"
            f"?$expand=teamsApp&$filter=teamsApp/id eq '{teams_app_id}'"
        )
        async with session.get(url, headers=headers) as resp:
            installations = (await resp.json()).get("value", [])
            if not installations:
                return None
            installation_id = installations[0]["id"]

        # Get chat ID
        async with session.get(
            f"https://graph.microsoft.com/v1.0/users/{user_id}"
            f"/teamwork/installedApps/{installation_id}/chat",
            headers=headers,
        ) as resp:
            return (await resp.json())["id"]
```

---

## Getting User Entra Object IDs

### Via Microsoft Graph API

```http
# List all users
GET https://graph.microsoft.com/v1.0/users?$select=id,displayName,mail,userPrincipalName
Authorization: Bearer {graph_token}

# Search by email
GET https://graph.microsoft.com/v1.0/users?$filter=mail eq 'john@contoso.com'&$select=id,displayName,mail

# Get single user by UPN
GET https://graph.microsoft.com/v1.0/users/john@contoso.com?$select=id,displayName,mail
```

The `id` field in the response is the `aadObjectId`.

### Python: List All Users with Pagination

```python
async def list_all_users(token: str) -> list[dict]:
    users = []
    url = "https://graph.microsoft.com/v1.0/users?$select=id,displayName,mail,userPrincipalName&$top=999"
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        while url:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                users.extend(data.get("value", []))
                url = data.get("@odata.nextLink")
    return users
```

### Via Azure Portal (Manual)

1. **portal.azure.com** → **Microsoft Entra ID** → **Users** → click user → **Object ID**
2. Or: **entra.microsoft.com** → **Users** → **Download users** (CSV export includes Object ID)

### Via PowerShell

```powershell
Connect-MgGraph -Scopes "User.Read.All"
Get-MgUser -All -Property Id, DisplayName, Mail | Select-Object Id, DisplayName, Mail
```

### Getting a Graph Access Token (Python)

```python
async def get_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }) as resp:
            return (await resp.json())["access_token"]
```

---

## Proactive App Installation via Graph

Install the bot for users who don't have it yet, so you can then send them proactive messages.

```python
async def install_app_for_user(graph_token: str, user_id: str, teams_app_id: str) -> int:
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/teamwork/installedApps"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers={
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json",
        }, json={
            "teamsApp@odata.bind": f"https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/{teams_app_id}"
        }) as resp:
            return resp.status  # 201 = success
```

After install, the bot receives a `conversationUpdate` event — capture the `ConversationReference` there.

**Requirements:**

- App must be in your org's app catalog or the Teams Store
- Permission: `TeamsAppInstallation.ReadWriteSelfForUser.All` (Application)
- Microsoft Entra admin must grant consent

---

## Python Sample Code

### Full Bot Application (aiohttp)

```python
# app.py
from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, MessageFactory
from botbuilder.schema import Activity

from bot import ProactiveBot  # Your bot handler class

APP_ID = "your-bot-app-id"
APP_PASSWORD = "your-bot-app-password"

SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

CONVERSATION_REFERENCES = {}  # Replace with DB in production
BOT = ProactiveBot(CONVERSATION_REFERENCES)


async def messages(req: web.Request) -> web.Response:
    """Handle incoming chat messages from Teams."""
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")
    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=201)


async def notify(req: web.Request) -> web.Response:
    """Send proactive message to all stored users."""
    body = await req.json()
    message_text = body.get("message", "Notification from bot")
    sent = 0
    for ref in CONVERSATION_REFERENCES.values():
        await ADAPTER.continue_conversation(
            ref,
            lambda tc: tc.send_activity(MessageFactory.text(message_text)),
            APP_ID,
        )
        sent += 1
    return web.json_response({"status": "ok", "sent": sent})


APP = web.Application()
APP.router.add_post("/api/messages", messages)
APP.router.add_post("/api/notify", notify)

if __name__ == "__main__":
    web.run_app(APP, host="0.0.0.0", port=3978)
```

### Send to All Members of a Team (from within a bot turn)

```python
from botbuilder.core.teams import TeamsInfo
from botbuilder.schema import ConversationParameters


async def message_all_team_members(turn_context: TurnContext, app_id: str, message: str):
    team_members = await TeamsInfo.get_paged_members(turn_context)
    conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)

    for member in team_members.members:
        conversation_parameters = ConversationParameters(
            is_group=False,
            bot=turn_context.activity.recipient,
            members=[member],
            tenant_id=turn_context.activity.conversation.tenant_id,
        )

        async def get_ref(tc1):
            ref = TurnContext.get_conversation_reference(tc1.activity)
            return await tc1.adapter.continue_conversation(ref, send_msg, app_id)

        async def send_msg(tc2: TurnContext):
            return await tc2.send_activity(f"Hello {member.name}. {message}")

        await turn_context.adapter.create_conversation(
            conversation_reference, get_ref, conversation_parameters
        )
```

---

## API Endpoints

### Your Bot Backend

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/messages` | Bot Framework messaging endpoint (set in Azure Bot registration) |
| POST | `/api/notify` | Trigger proactive broadcast (call from admin UI, scheduler, etc.) |

### Bot Connector REST API (called by your bot)

| Method | Path | Purpose |
|---|---|---|
| POST | `{serviceUrl}/v3/conversations` | Create a new 1:1 conversation |
| POST | `{serviceUrl}/v3/conversations/{id}/activities` | Send message to conversation |
| PUT | `{serviceUrl}/v3/conversations/{id}/activities/{activityId}` | Update a message |
| DELETE | `{serviceUrl}/v3/conversations/{id}/activities/{activityId}` | Delete a message |

### Microsoft Graph API (called by your backend)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1.0/users` | List all users (get aadObjectIds) |
| GET | `/v1.0/users/{id}/teamwork/installedApps` | Check if bot is installed for user |
| POST | `/v1.0/users/{id}/teamwork/installedApps` | Install bot for user |
| GET | `/v1.0/users/{id}/teamwork/installedApps/{installId}/chat` | Get chat ID for installed app |
| GET | `/v1.0/appCatalogs/teamsApps?$filter=externalId eq '{manifestId}'` | Get teamsAppId from catalog |

---

## Graph API Permissions Summary

| Permission | Type | Purpose |
|---|---|---|
| `User.Read.All` | Application | List users and read their profiles |
| `TeamsAppInstallation.ReadWriteSelfForUser.All` | Application | Install bot app for users, list installations |
| `Chat.Read.All` | Application | Read chat details (alternative for getting chatId) |

All application permissions require **admin consent**.

---

## Best Practices

### Welcome Messages

- Clearly explain WHY the user received the message
- Explain what the bot can do
- Provide next steps (e.g., "Type 'help' to see commands")

### Notification Messages

- State what happened / what triggered the notification
- Provide actionable next steps
- Include an opt-out path

### Technical

- **Always persist conversation references to a database** — not in-memory
- **Handle 403 errors gracefully** — user blocked/uninstalled the bot
- **Respect throttling** — use controlled concurrency (e.g., max 10 concurrent sends)
- **Keep serviceUrl fresh** — update on every incoming activity
- **Don't spam** — large teams (100+ members) can flag the bot as spam
- **Store conversationReference on every activity** — ensures freshness

### Scheduled Messages

- Respect user time zones
- Clearly state why the user is receiving the scheduled message

---

## Key Microsoft Docs References

| Topic | URL |
|---|---|
| Bot overview | `https://learn.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots` |
| Proactive messages | `https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages` |
| Send proactive notifications (Bot Service) | `https://learn.microsoft.com/en-us/azure/bot-service/bot-builder-howto-proactive-message` |
| Proactive install via Graph | `https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/proactive-bots-and-messages/graph-proactive-bots-and-messages` |
| Bot Connector API reference | `https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference` |
| List users (Graph) | `https://learn.microsoft.com/en-us/graph/api/user-list` |
| Install app for user (Graph) | `https://learn.microsoft.com/en-us/graph/api/userteamwork-post-installedapps` |
| List installed apps (Graph) | `https://learn.microsoft.com/en-us/graph/api/userteamwork-list-installedapps` |
| Get chat (Graph) | `https://learn.microsoft.com/en-us/graph/api/chat-get` |
| App templates (Company Communicator) | `https://learn.microsoft.com/en-us/microsoftteams/platform/samples/app-templates` |
| Chatbot solution comparison | `https://learn.microsoft.com/en-us/azure/bot-service/bot-overview` |
| Teams conversation bot sample (Python) | `https://github.com/microsoft/BotBuilder-Samples/tree/main/samples/python/57.teams-conversation-bot` |
| Proactive messages sample (Python) | `https://github.com/microsoft/BotBuilder-Samples/tree/master/samples/python/16.proactive-messages` |

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `BOT_APP_ID` | Bot's Microsoft App ID (from App Registration) | `12345678-abcd-...` |
| `BOT_APP_PASSWORD` | Bot's client secret | `your-secret` |
| `TENANT_ID` | Your Microsoft 365 tenant ID | `abcd1234-...` |
| `TEAMS_APP_ID` | App's ID in the Teams catalog (for Graph installs) | `b1c5353a-...` |
| `SERVICE_URL` | Teams service URL for proactive messages | `https://smba.trafficmanager.net/teams/` |
| `DATABASE_URL` | Connection string for conversation reference storage | `postgresql://...` |

---

## Migration Note: Bot Framework SDK → Agents SDK

The Bot Framework SDK was archived December 2025. For new projects, consider:

- **Microsoft 365 Agents SDK** (`aka.ms/agents`) — successor, supports C#, JS, Python
- **Microsoft Copilot Studio** — SaaS no-code/low-code option

Core proactive messaging concepts (conversation references, continue_conversation, Bot Connector API) remain the same in the Agents SDK.
