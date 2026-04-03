# Zotero AI Organizer

**Automated library organization using Anthropic Claude and the Zotero API.**

This tool leverages Large Language Models (LLMs) to automatically tag your research papers, design a cohesive collection hierarchy, and sort your items into that structure.

## Thanks to @ypsilonkah

Thanks to @ypsilonkah for the great improvements in his fork https://github.com/ypsilonkah/Zotero-AI-organizer, in particular for migrating the write operations to the Zotero Web API, which fixed the sync issues caused by direct SQLite edits.

Cf. for a potential problem here: https://forums.zotero.org/discussion/125783/not-a-valid-collection-key-upon-syncing

## Which version should I use?

**This version (v2.0-api) requires a Zotero account with cloud sync enabled.** It uses the [Zotero Web API](https://www.zotero.org/support/dev/web_api/v3/start), which communicates with zotero.org servers — it does not work with a local-only Zotero installation.

If you do not use Zotero cloud sync, use the [v1.0-sqlite](https://github.com/pastorpflores/Zotero-AI-organizer/tree/v1.0-sqlite) tag instead. That version modifies the SQLite database directly and works fully offline. However, be aware that the Zotero team strongly recommends never modifying the SQLite database directly, as it can lead to data corruption and sync issues. Use it at your own risk and always back up your `zotero.sqlite` file first.

## 🚀 Key Changes: API Integration

**Important Update:** Unlike previous versions that modified the SQLite database directly, this version uses the **Zotero Web API** for all write operations (creating collections, moving items, adding tags).

- **Reads** data locally (fast) or via API.
- **Writes** data via API (safe, sync-friendly).

This ensures database integrity and works seamlessly with Zotero Sync.

---

## 1. What is this project?

Zotero AI Organizer is a Python utility for researchers and students who have a large, messy Zotero library. Instead of manually dragging thousands of PDFs into folders, this tool acts as an intelligent librarian. It reads your papers, understands their content, and reorganizes them into a logical subject hierarchy.

## 2. How it works

The process works in four distinct stages:

1.  **Tagging (`keywords`):** The tool analyzes the title and abstract of every unfiled paper in your library. It sends this data to Anthropic's Claude, which generates standardized, high-quality keywords/tags for each paper.
2.  **Structuring (`propose`):** It looks at _all_ the keywords in your library to understand the breadth of your research. It then asks the AI to design a folder structure (taxonomy) that best fits your specific collection of papers.
3.  **Building (`implement`):** It connects to your Zotero account via the Web API and creates the actual Collection (folder) structure defined in the previous step.
4.  **Filing (`classify`):** Finally, it looks at every paper again and asks the AI, "Given this paper's content and our new folder structure, where does it belong?" It then moves the paper into the correct collection.

## 3. Setup

### Prerequisites

- Python 3.8+
- A Zotero Account (synced library)
- An Anthropic API Key (for Claude)

### Installation

1.  Clone this repository.
2.  Install required packages:
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

Create a `config.json` file in the root directory. You will need API keys from both Zotero and Anthropic.

```bash
cp ./config.example.json ./config.json
```

**To get Zotero Credentials:**

1.  Go to [Zotero API Settings](https://www.zotero.org/settings/keys).
2.  Create a new key with **Write Access**.
3.  Your `user_id` is also displayed on that page (next to "Your userID for use in API calls").

**config.json:**

```json
{
  "zotero_db_path": "/path/to/zotero.sqlite",
  "zotero_user_id": "zotero-userID",
  "zotero_api_key": "zotero-APIkey",
  "anthropic_api_key": "sk-ant-Your-Anthropic-API-Key",
  "model": "claude-haiku-4-5-20251001",
  "api_pricing": {
    "input": 0.8,
    "cache_write": 1.0,
    "cache_read": 0.08,
    "output": 4.0
  },
  "item_types": [
    "journalArticle",
    "book",
    "bookSection",
    "conferencePaper",
    "report"
  ]
}
```

_Note: `zotero_db_path` is used for fast reading. If not provided, the tool attempts to find the default location._

## 4. How to Use

Run the script using the different commands in sequence.

### Step 1: Generate Keywords

Scans your library and adds AI-generated tags to items that don't have them.

```bash
python main.py keywords
```

### Step 2: Propose Structure

Analyzes all keywords and generates a JSON file representing a proposed folder structure.

```bash
python main.py propose --output proposal.json
```

_You can open `proposal.json` and manually edit the folder names or hierarchy before proceeding._

### Step 3: Implement Structure

**Warning:** This will delete existing collections (if configured to do so in code) or create new ones via the Zotero API.

```bash
python main.py implement proposal.json
```

### Step 4: Classify Papers

Moves your papers into the newly created collections based on their content.

```bash

python main.py classify

```

Use the `--force` flag to re-classify papers that are already in collections (e.g., if you updated the structure):

```bash

python main.py classify --force

```

---

**Backup Warning:** While using the API is safer than direct DB editing, always back up your `zotero.sqlite` file before performing bulk automated organization.
