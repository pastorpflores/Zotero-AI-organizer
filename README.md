# Zotero Library Organizer

> [!WARNING]
> **This tool is currently broken and will corrupt Zotero cloud sync.**
>
> This tool modifies Zotero's SQLite database directly, bypassing Zotero's internal sync machinery. As reported in the [Zotero forums](https://forums.zotero.org/discussion/125783/not-a-valid-collection-key-upon-syncing), external tools that write to the database directly can produce invalid collection keys (e.g. `'WZ856FQ0' is not a valid collection key`) and corrupt the sync state between your local library and Zotero servers.
>
> **Consequences of using this tool in its current state:**
> - Zotero cloud sync will fail with "not a valid collection key" errors
> - Collections created by this tool may not be recognized by Zotero's sync server
> - You may need to restore from a backup to recover a clean sync state
>
> A rewrite using the [Zotero Web API](https://www.zotero.org/support/dev/web_api/v3/start) is needed to fix this. Do not use this tool until that rewrite is complete.
> In the meantime, **always back up your `zotero.sqlite` file before running any command**.

A Python tool to organize Zotero libraries using AI-powered classification and keyword generation.

## Components

### ZoteroLibrary (zotero_connector.py)
Manages direct interaction with Zotero's SQLite database:
- Read library structure (collections and papers)
- Create/delete collections
- Update paper metadata (keywords, collections)
- Modify collection hierarchy

### LibraryOrganizer (library_organizer.py)
Provides AI-powered organization using the Anthropic Claude API:
- Generate relevant keywords for papers
- Propose hierarchical collection structures
- Classify papers into appropriate collections
- Calculate API usage costs

## Installation

1. Clone the repository
2. Install required packages:
```bash
pip install anthropic sqlite3
```
3. Create a config.json file:
```json
{
    "zotero_db_path": "/path/to/your/zotero.sqlite",
    "anthropic_api_key": "your-api-key-here",
    "model": "claude-3-haiku-20240307",
    "api_pricing": {
        "input": 0.80,
        "cache_write": 1.00,
        "cache_read": 0.08,
        "output": 4.00
    }
}
```

## Usage

The tool provides several commands through main.py:

```bash
# Generate keywords for unclassified papers
python main.py keywords

# Generate collection structure proposal
python main.py propose --output proposal.json

# Review and edit proposal.json manually if needed

# Implement the new collection structure
python main.py implement proposal.json

# Classify unclassified papers into new structure
python main.py classify
```

### Typical Workflow

1. Add new papers to your Zotero library
2. Generate keywords for unclassified papers
```bash
python main.py keywords
```

3. If needed, generate a new collection structure proposal
```bash
python main.py propose --output new_structure.json
```

4. Review and edit new_structure.json
5. Apply the new structure
```bash
python main.py implement new_structure.json
```

6. Classify papers into the new structure
```bash
python main.py classify
```

## Configuration

The config.json file requires:
- `zotero_db_path`: Path to your Zotero SQLite database
- `anthropic_api_key`: Your Anthropic API key
- `model`: Claude model to use (e.g., "claude-3-haiku-20240307")
- `api_pricing`: Current API pricing in USD per 1M tokens

## Caution

- Always backup your Zotero database before using this tool
- Review generated keywords and collection proposals before implementation
- Monitor API usage costs through the Anthropic dashboard

## License

GNU AFFERO GENERAL PUBLIC LICENSE