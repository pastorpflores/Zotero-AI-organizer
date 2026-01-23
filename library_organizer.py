import json
from dataclasses import dataclass
from typing import Dict, List

import anthropic

from zotero_connector import ZoteroLibrary


@dataclass
class ApiPricing:
    input_price: float
    cache_write_price: float
    cache_read_price: float
    output_price: float


class LibraryOrganizer:
    def __init__(self, config: dict, field_context: str = ""):
        self.client = anthropic.Client(api_key=config['anthropic_api_key'])
        self.model = config['model']
        self.field_context = field_context
        self.pricing = ApiPricing(
            input_price=config['api_pricing']['input'],
            cache_write_price=config['api_pricing']['cache_write'],
            cache_read_price=config['api_pricing']['cache_read'],
            output_price=config['api_pricing']['output']
        )

    def _get_item_label(self, item_type: str) -> str:
        """Get human-readable label for item type."""
        labels = {
            'journalArticle': 'research paper',
            'book': 'book',
            'bookSection': 'book chapter',
            'conferencePaper': 'conference paper',
            'thesis': 'thesis',
            'preprint': 'preprint',
            'report': 'technical report',
            'manuscript': 'manuscript',
            'patent': 'patent',
            'webpage': 'webpage',
            'blogPost': 'blog post',
            'presentation': 'presentation',
        }
        return labels.get(item_type, 'publication')

    def improve_paper_keywords(self, paper_id: int, library: ZoteroLibrary) -> List[str]:
        item = library.items[paper_id]
        item_label = self._get_item_label(item.item_type)

        prompt = f"""Suggest 10 generic, reusable keywords for this {item_label}.
        Terms should focus on the main topic, method, technique, concept, or subject.
        Not too broad terms. Don't generate too similar keywords (e.g. INSTEAD 
        OF 'neo-institutionalism', 'institutional theoy', 'social institutions'
        just tag 'Neo-Institutionalism')
        Include only the most relevant keywords. If you are missing the abstract,
        don't state that you have no access to it. Just add keywords from the
        title instead, as far as possible.

        Title: {item.title}
        {"Abstract: " + item.abstract if item.abstract else ""}
        Type: {item.item_type}

        List only keywords, one per line."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        raw_lines = [k.strip() for k in response.content[0].text.split('\n') if k.strip()]
        new_keywords = []
        
        for line in raw_lines:
            # Filter out obvious conversational noise or refusals
            if len(line) > 100:
                continue
            
            lower_line = line.lower()
            if lower_line.startswith(("i don't", "i can't", "i cannot", "sorry", "here are", "sure, here", "unfortunately", "# Keywords", "#")):
                continue
                
            # Remove common list enumerations (1. , - , *)
            clean_line = line.lstrip("0123456789.-*• ")
            
            if clean_line:
                new_keywords.append(clean_line)

        if new_keywords:
            try:
                library.update_item_keywords(paper_id, new_keywords)
                print(f"Added {len(new_keywords)} keywords to item {paper_id}")
            except Exception as e:
                print(f"Failed to update keywords for item {paper_id}: {e}")
        else:
            print(f"No valid keywords extracted for item {paper_id}. Raw response: {response.content[0].text[:100]}...")
            
        return new_keywords

    def propose_collection_structure(self, library: ZoteroLibrary) -> Dict:
        keywords = sorted(library.get_all_keywords())
        keywords_str = "\n".join(keywords)

        # Analyze item type distribution
        type_counts = {}
        for item in library.items.values():
            type_counts[item.item_type] = type_counts.get(item.item_type, 0) + 1

        type_summary = ", ".join([f"{count} {t}s" for t, count in type_counts.items()])

        prompt = f"""Given these keywords from a research library:
        {keywords_str}

        Library contains: {type_summary}

        {self.field_context if self.field_context else ''}

        Create a hierarchical collection structure as JSON to organize publications with these topics.
        The structure should work well for different publication types (articles, books, reports, etc.).
        Return ONLY valid JSON, with no trailing commas. Limit the proposal to a maximum 100 total collections.
        If a sub-collection is located with a parent collection called Battery Aging, don't repeat the word
        Battery Aging in the sub-collection name, subcollection example: Aging Mechanisms, Black box Modelling..."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            text = response.content[0].text
            # Clean the text
            text = text.strip()
            # Remove any markdown formatting
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
                text = text.strip()

            # Find the complete JSON object
            start = text.find('{')
            count = 0
            end = start

            for i in range(start, len(text)):
                if text[i] == '{':
                    count += 1
                elif text[i] == '}':
                    count -= 1
                    if count == 0:
                        end = i + 1
                        break

            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("Could not find complete JSON object")

        except Exception as e:
            print(f"Error parsing JSON: {e}")
            print("Raw response:", text[:200] + "..." if len(text) > 200 else text)
            return {"Error": "Failed to parse structure"}

    def save_proposal(self, structure: Dict, filepath: str = "collection_proposal.json") -> bool:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)
            print(f"Saved proposal to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving proposal: {e}")
            return False

    def implement_collection_structure(self, structure: Dict, library: ZoteroLibrary) -> None:
        """Implement the proposed collection structure in Zotero."""
        try:
            # Delete existing collections
            library.delete_all_collections()

            # Handle structure with top-level "collections" key
            if 'collections' in structure and isinstance(structure['collections'], list):
                collections_to_create = structure['collections']
            else:
                collections_to_create = structure

            # Create new structure
            collection_map = library.create_collection_structure(collections_to_create)
            print(f"Successfully created {len(collection_map)} collections")

        except Exception as e:
            print(f"Error implementing collection structure: {e}")
            raise

    def classify_paper_in_collections(self, paper_id: int, library: ZoteroLibrary,
                                      structure_file: str = 'proposal.json') -> None:
        """Classify a paper into appropriate collections using the LLM and update Zotero."""
        item = library.items[paper_id]

        # Get flattened collection structure
        collection_paths = []
        collection_map = {}  # Map paths to collection Keys

        def flatten_collections(structure, prefix: str = ""):
            """Flatten collection structure supporting both dict and array formats."""
            # Handle array-based structure
            if isinstance(structure, list):
                for item in structure:
                    if isinstance(item, dict) and 'name' in item:
                        name = item['name']
                        full_path = f"{prefix}/{name}" if prefix else name
                        collection_paths.append(full_path)
                        # Map path to collection Key
                        for coll in library.collections.values():
                            if coll.name == name:
                                collection_map[full_path] = coll.key
                                break
                        # Recursively process subcollections
                        if 'subcollections' in item and item['subcollections']:
                            flatten_collections(item['subcollections'], full_path)

            # Handle dict-based structure (original format)
            elif isinstance(structure, dict):
                for name, content in structure.items():
                    full_path = f"{prefix}/{name}" if prefix else name
                    collection_paths.append(full_path)
                    # Map path to collection Key
                    for coll in library.collections.values():
                        if coll.name == name:
                            collection_map[full_path] = coll.key
                            break
                    if isinstance(content, dict):
                        flatten_collections(content, full_path)

        # Load and flatten the collection structure
        with open(structure_file, 'r') as f:
            structure = json.load(f)

        # Handle structure with top-level "collections" key
        if 'collections' in structure and isinstance(structure['collections'], list):
            flatten_collections(structure['collections'])
        else:
            flatten_collections(structure)

        print(f"Loaded {len(collection_paths)} collection paths from {structure_file}")
        print(f"Mapped {len(collection_map)} collections to IDs")

        if not collection_paths:
            print("Warning: No collection paths found in structure file!")
            return

        # Get collection suggestions from LLM
        item_type_label = self._get_item_label(item.item_type)

        prompt = f"""Given this {item_type_label}:
        Title: {item.title}
        {"Abstract: " + item.abstract if item.abstract else ""}
        Keywords: {', '.join(item.keywords)}
        Type: {item.item_type}

        And these available collections:
        {chr(10).join(collection_paths)}

        List the most appropriate collections for this publication.
        Output only the exact collection paths, one per line.
        Choose between 1-3 most relevant collections."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        # Update paper collections in Zotero
        llm_response = response.content[0].text
        print(f"LLM suggested collections:\n{llm_response}")

        collections = [line.strip() for line in llm_response.split('\n') if line.strip()]
        collection_keys = []
        for c in collections:
            if c in collection_map:
                collection_keys.append(collection_map[c])
            else:
                print(f"Warning: Collection '{c}' not found in collection_map")

        if collection_keys:
            library.update_item_collections(paper_id, collection_keys)
            matched_names = [library.collections[cid].name for cid in collection_keys if cid in library.collections]
            print(f"Successfully classified into: {matched_names}")
        else:
            print("No matching collections found - paper not classified")
