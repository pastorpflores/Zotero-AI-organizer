import anthropic
import json
from typing import List, Dict
from zotero_connector import ZoteroLibrary
from dataclasses import dataclass


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

    def improve_paper_keywords(self, paper_id: int, library: ZoteroLibrary) -> List[str]:
        item = library.items[paper_id]

        prompt = f"""Suggest generic, reusable keywords for this paper. Terms should focus on the main process,
        technique, or concept, no too broad terms. Include only the most relevant keywords.:
        Title: {item.title}
        Abstract: {item.abstract}
        List only keywords, one per line."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        new_keywords = [k.strip() for k in response.content[0].text.split('\n') if k.strip()]
        library.update_item_keywords(paper_id, new_keywords)
        return new_keywords

    def propose_collection_structure(self, library: ZoteroLibrary) -> Dict:
        keywords = sorted(library.get_all_keywords())
        keywords_str = "\n".join(keywords)

        prompt = f"""Given these keywords from a research paper library:
        {keywords_str}

        {self.field_context if self.field_context else ''}

        Create a hierarchical collection structure as JSON to organize papers with these topics.
        Return ONLY valid JSON, with no trailing commas. Limit the proposal to a maximum 100 total collections.
        If a sub-collection is located with a parent collection called Battery Aging, don't repeat the word
        Battery Aging in the sub-collection name, subcollection example: Aging Mechanisms, Black box Modelling..."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
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

            # Create new structure
            collection_map = library.create_collection_structure(structure)
            print(f"Successfully created {len(collection_map)} collections")

        except Exception as e:
            print(f"Error implementing collection structure: {e}")
            raise

    def classify_paper_in_collections(self, paper_id: int, library: ZoteroLibrary) -> None:
        """Classify a paper into appropriate collections using the LLM and update Zotero."""
        item = library.items[paper_id]

        # Get flattened collection structure
        collection_paths = []
        collection_map = {}  # Map paths to collection IDs

        def flatten_collections(structure: dict, prefix: str = ""):
            for name, content in structure.items():
                full_path = f"{prefix}/{name}" if prefix else name
                collection_paths.append(full_path)
                # Map path to collection ID
                for coll in library.collections.values():
                    if coll.name == name:
                        collection_map[full_path] = coll.collection_id
                if isinstance(content, dict):
                    flatten_collections(content, full_path)

        with open('my_proposal.json', 'r') as f:
            structure = json.load(f)
        flatten_collections(structure)

        # Get collection suggestions from LLM
        prompt = f"""Given this paper:
        Title: {item.title}
        Abstract: {item.abstract}
        Keywords: {', '.join(item.keywords)}

        And these available collections:
        {chr(10).join(collection_paths)}

        List the most appropriate collections for this paper. Output only the exact collection paths, one per line.
        Choose between 1-3 most relevant collections."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        # Update paper collections in Zotero
        collections = [line.strip() for line in response.content[0].text.split('\n') if line.strip()]
        collection_ids = [collection_map[c] for c in collections if c in collection_map]
        if collection_ids:
            library.update_item_collections(paper_id, collection_ids)
            print(f"Updated collections for paper: {collections}")
        else:
            print("No matching collections found")
