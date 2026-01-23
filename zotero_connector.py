import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from pyzotero import zotero


@dataclass
class ZoteroItem:
    """Represents a paper/item in the Zotero library."""
    item_id: int
    key: str
    title: str
    keywords: List[str]
    abstract: str
    collections: List[str]
    item_type: str
    metadata: Dict[str, str] = None


class ZoteroCollection:
    """Represents a collection in the Zotero library."""
    def __init__(self, key: str, name: str, parent_key: Optional[str] = None):
        self.key = key
        self.name = name
        self.parent_key = parent_key
        self.items: List[ZoteroItem] = []


class ZoteroLibrary:
    """Main class to interact with Zotero SQLite database (Read) and API (Write)."""

    def __init__(self, db_path: str = None, item_types: List[str] = None, 
                 zotero_user_id: str = None, zotero_api_key: str = None):
        self.db_path = self._find_db_path(db_path)
        self.collections: Dict[str, ZoteroCollection] = {}
        self.items: Dict[int, ZoteroItem] = {}
        self.library_id = None
        self._db_collection_id_map: Dict[int, str] = {} # Map local int ID to key

        # API Client
        if zotero_user_id and zotero_api_key:
            try:
                self.zot = zotero.Zotero(zotero_user_id, 'user', zotero_api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Zotero API client: {e}")
                self.zot = None
        else:
            print("Warning: Zotero API credentials not provided. Write operations will fail.")
            self.zot = None

        self.item_types = item_types if item_types else ['journalArticle']
        self.excluded_types = {'note', 'attachment', 'annotation'}

    def _find_db_path(self, db_path: Optional[str]) -> str:
        if db_path and os.path.exists(db_path):
            return db_path
        home = str(Path.home())
        zotero_dir = os.path.join(home, '.zotero/zotero')
        if os.path.exists(zotero_dir):
            profiles = [d for d in os.listdir(zotero_dir) if d.endswith('.default')]
            if profiles:
                default_path = os.path.join(zotero_dir, profiles[0], 'zotero.sqlite')
                if os.path.exists(default_path):
                    return default_path
        raise FileNotFoundError("Could not find Zotero database.")

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def load_library(self) -> None:
        """Load library data."""
        with self.connect() as conn:
            self._detect_library_id(conn)
            
            # Prefer API for collections to ensure fresh state
            loaded_from_api = False
            if self.zot:
                try:
                    print("Fetching collections from Zotero API...")
                    self._load_collections_from_api()
                    loaded_from_api = True
                except Exception as e:
                    print(f"Failed to fetch from API ({e}), falling back to database.")
            
            if not loaded_from_api:
                self._load_collections_from_db(conn)

            self._load_items(conn)
            
            # Only load DB relationships if we are using DB collections
            # Otherwise, we can't map local IDs to API keys reliably without sync
            if not loaded_from_api:
                self._load_collection_items(conn)

    def _detect_library_id(self, conn: sqlite3.Connection) -> None:
        type_placeholders = ','.join(['?' for _ in self.item_types])
        cursor = conn.execute(f"""
            SELECT DISTINCT i.libraryID
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE it.typeName IN ({type_placeholders})
            LIMIT 1
        """, tuple(self.item_types))
        result = cursor.fetchone()
        self.library_id = result[0] if result else 1

    def _load_collections_from_api(self) -> None:
        """Load collections from API."""
        # limit=None fetches all
        colls = self.zot.collections(limit=None)
        for c in colls:
            data = c['data']
            key = data['key']
            name = data['name']
            parent = data.get('parentCollection')
            if parent == False: parent = None # pyzotero sometimes returns False
            
            self.collections[key] = ZoteroCollection(key, name, parent)

    def _load_collections_from_db(self, conn: sqlite3.Connection) -> None:
        """Load collections from database."""
        cursor = conn.execute("""
            SELECT collectionID, key, collectionName, parentCollectionID
            FROM collections
            WHERE libraryID = ?
        """, (self.library_id,))
        
        # We need a temporary map of ID -> Key to resolve parents
        temp_map = {}
        raw_colls = []
        
        for collection_id, key, name, parent_id in cursor.fetchall():
            temp_map[collection_id] = key
            self._db_collection_id_map[collection_id] = key
            raw_colls.append((key, name, parent_id))
            
        for key, name, parent_id in raw_colls:
            parent_key = temp_map.get(parent_id) if parent_id else None
            self.collections[key] = ZoteroCollection(key, name, parent_key)

    def _load_items(self, conn: sqlite3.Connection) -> None:
        type_placeholders = ','.join(['?' for _ in self.item_types])
        cursor = conn.execute(f"""
            SELECT
                i.itemID, i.key, it.typeName,
                (SELECT iv.value FROM itemData id JOIN itemDataValues iv ON id.valueID = iv.valueID WHERE id.itemID = i.itemID AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title') LIMIT 1) as title,
                (SELECT iv.value FROM itemData id JOIN itemDataValues iv ON id.valueID = iv.valueID WHERE id.itemID = i.itemID AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'abstractNote') LIMIT 1) as abstract,
                (SELECT iv.value FROM itemData id JOIN itemDataValues iv ON id.valueID = iv.valueID WHERE id.itemID = i.itemID AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'extra') LIMIT 1) as extra,
                (SELECT GROUP_CONCAT(t.name, '; ') FROM itemTags it JOIN tags t ON it.tagID = t.tagID WHERE it.itemID = i.itemID) as keywords
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE it.typeName IN ({type_placeholders})
            AND i.libraryID = ?
        """, tuple(self.item_types) + (self.library_id,))

        for item_id, key, item_type, title, abstract, extra, keywords in cursor.fetchall():
            if title:
                primary_text = abstract if abstract else (extra or "")
                keywords_list = keywords.split('; ') if keywords else []
                self.items[item_id] = ZoteroItem(item_id, key, title, keywords_list, primary_text, [], item_type, {})

    def _load_collection_items(self, conn: sqlite3.Connection) -> None:
        """Load relationships. Only useful if collections were loaded from DB."""
        cursor = conn.execute("SELECT collectionID, itemID FROM collectionItems")
        for collection_id, item_id in cursor.fetchall():
            if collection_id in self._db_collection_id_map and item_id in self.items:
                collection_key = self._db_collection_id_map[collection_id]
                if collection_key in self.collections:
                    collection = self.collections[collection_key]
                    item = self.items[item_id]
                    collection.items.append(item)
                    item.collections.append(collection.name)

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> str:
        """Create new collection in Zotero via API. Returns Key."""
        if not self.zot: raise RuntimeError("API not initialized")

        payload = {'name': name}
        if parent_key:
            if parent_key not in self.collections:
                raise ValueError(f"Parent {parent_key} not found")
            payload['parentCollection'] = parent_key

        try:
            resp = self.zot.create_collections([payload])
            if resp and 'successful' in resp and resp['successful']:
                new_key = list(resp['successful'].keys())[0]
                self.collections[new_key] = ZoteroCollection(new_key, name, parent_key)
                return new_key
            else:
                raise RuntimeError(f"Failed to create collection: {resp}")
        except Exception as e:
            raise RuntimeError(f"API Error: {e}")

    def delete_collection(self, collection_key: str) -> None:
        if collection_key not in self.collections: raise ValueError("Collection not found")
        if not self.zot: raise RuntimeError("API not initialized")

        try:
            self.zot.delete_collection(collection_key)
            coll = self.collections.pop(collection_key)
            for item in coll.items:
                if coll.name in item.collections:
                    item.collections.remove(coll.name)
        except Exception as e:
            raise RuntimeError(f"API Error: {e}")

    def update_item_collections(self, item_id: int, collection_keys: List[str]) -> None:
        if item_id not in self.items: raise ValueError("Item not found")
        if not self.zot: raise RuntimeError("API not initialized")

        item = self.items[item_id]
        try:
            # We must fetch the item to update it safely (or use a patch if supported, but pyzotero uses PUT)
            current = self.zot.item(item.key)
            current['collections'] = collection_keys
            self.zot.update_item(current)
            
            # Update local
            item.collections = [self.collections[k].name for k in collection_keys if k in self.collections]
        except Exception as e:
            raise RuntimeError(f"API Error: {e}")

    def update_item_keywords(self, item_id: int, new_keywords: List[str]) -> None:
        if item_id not in self.items: raise ValueError("Item not found")
        if not self.zot: raise RuntimeError("API not initialized")
        
        item = self.items[item_id]
        try:
            zotero_item = self.zot.item(item.key)
            if 'data' in zotero_item and 'deleted' in zotero_item['data']:
                del zotero_item['data']['deleted']
            self.zot.add_tags(zotero_item, *new_keywords)
            item.keywords = list(set(item.keywords + new_keywords))
        except Exception as e:
            raise RuntimeError(f"API Error: {e}")

    def get_all_keywords(self) -> set[str]:
        all_keywords = set()
        for item in self.items.values():
            all_keywords.update(item.keywords)
        return all_keywords

    def delete_all_collections(self) -> None:
        if not self.zot: raise RuntimeError("API not initialized")
        
        # Get all keys currently known
        keys = list(self.collections.keys())
        print(f"Deleting {len(keys)} collections via API...")
        
        # Delete one by one (safest)
        for k in keys:
            try:
                self.zot.delete_collection(k)
            except:
                pass
        self.collections.clear()
        for item in self.items.values():
            item.collections.clear()

    def create_collection_structure(self, structure, parent_key: Optional[str] = None) -> Dict[str, str]:
        """Create structure. Returns Name -> Key map."""
        collection_map = {}
        
        if isinstance(structure, list):
            for item in structure:
                if isinstance(item, dict) and 'name' in item:
                    name = item['name']
                    key = self.create_collection(name, parent_key)
                    collection_map[name] = key
                    if 'subcollections' in item:
                        sub_map = self.create_collection_structure(item['subcollections'], key)
                        collection_map.update(sub_map)
        
        elif isinstance(structure, dict):
            for name, content in structure.items():
                key = self.create_collection(name, parent_key)
                collection_map[name] = key
                if isinstance(content, dict):
                    sub_map = self.create_collection_structure(content, key)
                    collection_map.update(sub_map)
                    
        return collection_map
