# Zotero Library Organizer

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
pip install anthropic
```
Note: `sqlite3` is part of Python's standard library and does not need to be installed separately.

3. Create a config.json file:
```json
{
    "zotero_db_path": "/path/to/your/zotero.sqlite",
    "anthropic_api_key": "your-api-key-here",
    "model": "claude-haiku-4-5-20251001",
    "api_pricing": {
        "input": 0.8,
        "cache_write": 1.0,
        "cache_read": 0.08,
        "output": 4.0
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

# Classify unclassified papers into new structure (uses proposal.json by default)
python main.py classify

# Classify using a custom structure file
python main.py classify --structure my_custom_structure.json
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
# Use default structure file (proposal.json)
python main.py classify

# Or use a specific structure file
python main.py classify --structure new_structure.json
```

## Configuration

The config.json file requires:
- `zotero_db_path`: Path to your Zotero SQLite database
- `anthropic_api_key`: Your Anthropic API key
- `model`: Claude model to use (e.g., "claude-haiku-4-5-20251001")
- `api_pricing`: Current API pricing in USD per 1M tokens

## Caution

- Always backup your Zotero database before using this tool
- Review generated keywords and collection proposals before implementation
- Monitor API usage costs through the Anthropic dashboard

## Recent Updates (December 2025)

### Model Update
- Upgraded to **claude-haiku-4-5-20251001** for improved performance
- Increased max_tokens from 4000 to 8000 for better handling of complex responses

### Enhanced Collection Structure Support
The tool now supports two JSON structure formats for maximum flexibility:

**1. Array-based format (recommended):**
```json
{
  "collections": [
    {
      "name": "Machine Learning",
      "subcollections": [
        {"name": "Deep Learning"},
        {"name": "Reinforcement Learning"}
      ]
    }
  ]
}
```

**2. Dict-based format (legacy):**
```json
{
  "Machine Learning": {
    "Deep Learning": {},
    "Reinforcement Learning": {}
  }
}
```

### Custom Structure Files for Classification
The `classify` command now supports custom structure files:
```bash
# Use default proposal.json
python main.py classify

# Use a different structure file
python main.py classify --structure my_alternative_structure.json
```

This allows you to:
- Test different collection structures without overwriting your main proposal
- Maintain multiple organizational schemes for different purposes
- Experiment with classification before committing to a structure

### Multi-Library Support
- **Automatic library detection**: The tool now automatically detects the correct library ID from your Zotero database
- **Safer operations**: All collection operations are scoped to the specific library, preventing accidental modifications to other libraries
- No manual configuration needed - the library ID is detected when loading the library

### Code Improvements

**library_organizer.py:**
- Enhanced `classify_paper_in_collections()` to accept custom structure files
- Improved error handling and logging during classification
- Better feedback when collections cannot be matched

**main.py:**
- Added `--structure` parameter to `classify` command
- Improved argument parsing and command routing

**zotero_connector.py:**
- Added automatic library ID detection via `_detect_library_id()` method
- Updated all SQL queries to filter by libraryID for multi-library safety
- Enhanced `create_collection_structure()` to handle both structure formats
- Improved `delete_all_collections()` to only affect the target library

## License

GNU AFFERO GENERAL PUBLIC LICENSE