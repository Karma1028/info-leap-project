# Notion Workspace — OxData Project Hub

This file is the single source of truth for the Notion setup.
Use it to update Notion from any session (Claude Code, Hermes, or manually).

---

## IDs Reference

| Resource | ID | URL |
|----------|----|-----|
| **Hub Page** | `34385aa8-f369-81a6-8cba-f5343e1555be` | https://www.notion.so/34385aa8f36981a68cbaf5343e1555be |
| **OxData Updates DB** | `abfbc4e98c0f450282f2e47a46b44ca5` | https://www.notion.so/abfbc4e98c0f450282f2e47a46b44ca5 |
| **Data Source (collection)** | `c64d8259-2ba4-47d8-82d3-c1573523ad1d` | `collection://c64d8259-2ba4-47d8-82d3-c1573523ad1d` |
| **Kanban Board view** | `34385aa8-f369-81aa-8c33-000c49e72b9c` | — |
| **Timeline view** | `34385aa8-f369-8169-be58-000cb19fa660` | — |
| **Calendar view** | `34385aa8-f369-8188-b2aa-000cee10649d` | — |
| **All Items view** | `34385aa8-f369-8157-8a75-000c6f4b37bc` | — |
| **📚 Documentation page** | `34385aa8-f369-8141-846b-d54e565e1d2f` | https://www.notion.so/34385aa8f3698141846bd54e565e1d2f |

### Documentation Sub-pages

| Doc | Notion Page ID | URL |
|-----|---------------|-----|
| Project Overview | `34385aa8-f369-8163-913b-dfe1fdadf0e6` | https://www.notion.so/34385aa8f3698163913bdfe1fdadf0e6 |
| Database Schema | `34385aa8-f369-8118-a4eb-ebb8ffdccf2c` | https://www.notion.so/34385aa8f3698118a4ebebb8ffdccf2c |
| Business Logic | `34385aa8-f369-81bf-9ce1-f82312b44aa9` | https://www.notion.so/34385aa8f36981bf9ce1f82312b44aa9 |
| Skill Foundry | `34385aa8-f369-815b-b4c7-db597fc7d773` | https://www.notion.so/34385aa8f369815bb4c7db597fc7d773 |
| API Context & Token Budget | `34385aa8-f369-810f-b30d-c538eed4af2b` | https://www.notion.so/34385aa8f369810fb30dc538eed4af2b |
| Progress Tracker | `34385aa8-f369-81c8-9735-f2bd635cca1c` | https://www.notion.so/34385aa8f36981c89735f2bd635cca1c |
| Bug Log | `34385aa8-f369-8163-8d8a-f5912c17d404` | https://www.notion.so/34385aa8f36981638d8af5912c17d404 |
| Test Report | `34385aa8-f369-81da-a00f-ddfbe2268a80` | https://www.notion.so/34385aa8f36981daa00fddfbe2268a80 |

---

## Database Schema (OxData Updates)

Properties used in the `OxData Updates` database (data_source_id: `c64d8259-2ba4-47d8-82d3-c1573523ad1d`):

```sql
CREATE TABLE (
  "Name"       TITLE,
  "Status"     SELECT('Not Started':gray, 'In Progress':blue, 'Done':green, 'Blocked':red, 'Deferred':yellow),
  "Category"   SELECT('Feature':purple, 'Bug Fix':red, 'Testing':orange, 'Docs':blue, 'Infrastructure':gray),
  "Priority"   SELECT('High':red, 'Medium':yellow, 'Low':gray),
  "Start Date" DATE,
  "Due Date"   DATE,
  "Session"    RICH_TEXT,   -- dev session label e.g. "2026-04-15"
  "Notes"      RICH_TEXT,   -- details, root causes, decisions
  "Task ID"    UNIQUE_ID PREFIX 'OX'
)
```

---

## How to Update from Claude Code

### Add a new item to the tracker

```
Use the Notion MCP tool: notion-create-pages
Parent: data_source_id = c64d8259-2ba4-47d8-82d3-c1573523ad1d

Properties:
  Name:               "<task name>"
  Status:             "Not Started" | "In Progress" | "Done" | "Blocked" | "Deferred"
  Category:           "Feature" | "Bug Fix" | "Testing" | "Docs" | "Infrastructure"
  Priority:           "High" | "Medium" | "Low"
  date:Start Date:start:  "YYYY-MM-DD"
  date:Due Date:start:    "YYYY-MM-DD"
  Session:            "YYYY-MM-DD"
  Notes:              "<details>"
```

### Update an existing item's status

```
Use the Notion MCP tool: notion-update-page
page_id: <item page ID>
command: update_properties
properties:
  Status: "Done"
  Notes:  "<updated notes>"
```

### Sync a doc page with the latest file content

```
Use the Notion MCP tool: notion-update-page
page_id: <doc page ID from the table above>
command: replace_content
new_str: <full markdown content of the updated file>
```

### Add a new database row for a whole session

Prompt to give Claude:
> "Read docs/PROGRESS.md, find the session dated YYYY-MM-DD, and add all new items
>  to the OxData Updates database in Notion using data_source_id
>  c64d8259-2ba4-47d8-82d3-c1573523ad1d"

---

## Sync Checklist (run after every dev session)

- [ ] Add new items to `OxData Updates` database (one row per feature/bug/task)
- [ ] Update `Status` of in-progress items that are now Done
- [ ] Update `Progress Tracker` Notion page to match `docs/PROGRESS.md`
- [ ] Update `Bug Log` Notion page if new bugs found or fixed
- [ ] If major architecture change: update `Project Overview`, `Skill Foundry`, or `API Context` page
- [ ] Commit `docs/NOTION.md` if any IDs change

---

## Structure Map

```
📊 OxData — Project Hub  (34385aa8-f369-81a6-8cba-f5343e1555be)
│
├── 📊 OxData Updates [INLINE DATABASE]  (abfbc4e98c0f450282f2e47a46b44ca5)
│   ├── 📋 Kanban Board    — grouped by Status
│   ├── 📅 Timeline        — gantt by Start Date → Due Date, grouped by Category
│   ├── 🗓️  Calendar        — by Due Date
│   └── 📊 All Items       — full table, sortable/filterable, shareable
│
└── 📚 Documentation  (34385aa8-f369-8141-846b-d54e565e1d2f)
    ├── 📋 Project Overview
    ├── 🗄️  Database Schema
    ├── 🧠 Business Logic
    ├── ⚙️  Skill Foundry
    ├── 🔌 API Context & Token Budget
    ├── 📈 Progress Tracker
    ├── 🐛 Bug Log
    └── 🧪 Test Report
```

---

## Notion MCP Server

This workspace is connected via the Notion MCP plugin in Claude Code.
Tool prefix: `mcp__d0c29291-11d9-4fbc-89dc-42d39060e468__`

Available tools:
- `notion-search` — search workspace
- `notion-fetch` — read any page/database by ID or URL
- `notion-create-pages` — add rows to DB or new pages
- `notion-update-page` — update properties or content
- `notion-create-database` — create a new database
- `notion-create-view` — add a view to an existing database
