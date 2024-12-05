import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ZoteroItem:
    """Represents a paper/item in the Zotero library."""
    item_id: int
    title: str
    keywords: List[str]
    abstract: str
    collections: List[str]


class ZoteroCollection:
    """Represents a collection in the Zotero library."""
    def __init__(self, collection_id: int, name: str, parent_id: Optional[int] = None):
        self.collection_id = collection_id
        self.name = name
        self.parent_id = parent_id
        self.items: List[ZoteroItem] = []


class ZoteroLibrary:
    """Main class to interact with Zotero SQLite database."""

    def __init__(self, db_path: str = None):
        self.db_path = self._find_db_path(db_path)
        self.collections: Dict[int, ZoteroCollection] = {}
        self.items: Dict[int, ZoteroItem] = {}
        self.library_id = 1  # Default library ID

    def _find_db_path(self, db_path: Optional[str]) -> str:
        """Locate Zotero database file."""
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

        raise FileNotFoundError("Could not find Zotero database. Please specify path manually.")

    def connect(self) -> sqlite3.Connection:
        """Create connection to Zotero database."""
        return sqlite3.connect(self.db_path)

    def load_library(self) -> None:
        """Load all collections and items from database."""
        with self.connect() as conn:
            self._load_collections(conn)
            self._load_items(conn)
            self._load_collection_items(conn)

    def _load_collections(self, conn: sqlite3.Connection) -> None:
        """Load collections from database."""
        cursor = conn.execute("""
            SELECT collectionID, collectionName, parentCollectionID
            FROM collections
        """)
        for collection_id, name, parent_id in cursor.fetchall():
            self.collections[collection_id] = ZoteroCollection(collection_id, name, parent_id)

    def _load_items(self, conn: sqlite3.Connection) -> None:
        """Load items from database."""
        cursor = conn.execute("""
            SELECT i.itemID,
                (SELECT iv.value FROM itemData id
                    JOIN itemDataValues iv ON id.valueID = iv.valueID
                    WHERE id.itemID = i.itemID
                    AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
                    LIMIT 1) as title,
                (SELECT iv.value FROM itemData id
                    JOIN itemDataValues iv ON id.valueID = iv.valueID
                    WHERE id.itemID = i.itemID
                    AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'abstractNote')
                    LIMIT 1) as abstract,
                (SELECT GROUP_CONCAT(t.name, '; ')
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = i.itemID) as keywords
            FROM items i
            WHERE i.itemTypeID = (SELECT itemTypeID FROM itemTypes WHERE typeName = 'journalArticle')
        """)

        for item_id, title, abstract, keywords in cursor.fetchall():
            if title:
                keywords_list = keywords.split('; ') if keywords else []
                self.items[item_id] = ZoteroItem(
                    item_id=item_id,
                    title=title,
                    keywords=keywords_list,
                    abstract=abstract or "",
                    collections=[]
                )

    def _load_collection_items(self, conn: sqlite3.Connection) -> None:
        """Load collection-item relationships."""
        cursor = conn.execute("SELECT collectionID, itemID FROM collectionItems")
        for collection_id, item_id in cursor.fetchall():
            if collection_id in self.collections and item_id in self.items:
                collection = self.collections[collection_id]
                item = self.items[item_id]
                collection.items.append(item)
                item.collections.append(collection.name)

    def create_collection(self, name: str, parent_id: Optional[int] = None) -> int:
        """Create new collection in Zotero."""
        with self.connect() as conn:
            # Generate a unique key (8 random uppercase letters and numbers)
            import random
            import string
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

            cursor = conn.execute(
                "INSERT INTO collections (collectionName, parentCollectionID, libraryID, key) VALUES (?, ?, ?, ?)",
                (name, parent_id, self.library_id, key)
            )
            collection_id = cursor.lastrowid
            self.collections[collection_id] = ZoteroCollection(collection_id, name, parent_id)
            return collection_id

    def delete_collection(self, collection_id: int) -> None:
        """Delete collection and update items."""
        if collection_id not in self.collections:
            raise ValueError(f"Collection {collection_id} not found")

        with self.connect() as conn:
            # Remove collection-item relationships
            conn.execute("DELETE FROM collectionItems WHERE collectionID = ?", (collection_id,))
            # Delete collection
            conn.execute("DELETE FROM collections WHERE collectionID = ?", (collection_id,))

            # Update local data
            collection = self.collections[collection_id]
            for item in collection.items:
                item.collections.remove(collection.name)
            del self.collections[collection_id]

    def move_collection(self, collection_id: int, new_parent_id: Optional[int]) -> None:
        """Move collection to new parent."""
        if collection_id not in self.collections:
            raise ValueError(f"Collection {collection_id} not found")
        if new_parent_id and new_parent_id not in self.collections:
            raise ValueError(f"Parent collection {new_parent_id} not found")

        with self.connect() as conn:
            conn.execute(
                "UPDATE collections SET parentCollectionID = ? WHERE collectionID = ?",
                (new_parent_id, collection_id)
            )
            self.collections[collection_id].parent_id = new_parent_id

    def update_item_collections(self, item_id: int, collection_ids: List[int]) -> None:
        if item_id not in self.items:
            raise ValueError(f"Item {item_id} not found")

        with self.connect() as conn:
            conn.execute("DELETE FROM collectionItems WHERE itemID = ?", (item_id,))

            for i, coll_id in enumerate(collection_ids):
                if coll_id in self.collections:
                    conn.execute(
                        "INSERT INTO collectionItems (itemID, collectionID, orderIndex) VALUES (?, ?, ?)",
                        (item_id, coll_id, i)
                    )

            item = self.items[item_id]
            item.collections = [self.collections[cid].name for cid in collection_ids if cid in self.collections]

    def update_item_keywords(self, item_id: int, new_keywords: List[str]) -> None:
        if item_id not in self.items:
            raise ValueError(f"Item {item_id} not found")

        # Combine existing and new keywords, remove duplicates
        combined_keywords = list(set(self.items[item_id].keywords + new_keywords))

        with self.connect() as conn:
            # Clear existing tag relationships
            conn.execute("DELETE FROM itemTags WHERE itemID = ?", (item_id,))

            # Add all keywords
            for keyword in combined_keywords:
                cursor = conn.execute("SELECT tagID FROM tags WHERE name = ?", (keyword,))
                tag_id = cursor.fetchone()

                if not tag_id:
                    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (keyword,))
                    tag_id = cursor.lastrowid
                else:
                    tag_id = tag_id[0]

                conn.execute("INSERT INTO itemTags (itemID, tagID, type) VALUES (?, ?, 0)", (item_id, tag_id))

            self.items[item_id].keywords = combined_keywords

    def get_all_keywords(self) -> set[str]:
        """Get all unique keywords from all items in the library."""
        all_keywords = set()
        for item in self.items.values():
            all_keywords.update(item.keywords)
        return all_keywords

    def delete_all_collections(self) -> None:
        """Delete all collections from the library."""
        with self.connect() as conn:
            conn.execute("DELETE FROM collectionItems")
            conn.execute(f"DELETE FROM collections WHERE libraryID = {self.library_id}")
            self.collections.clear()
            for item in self.items.values():
                item.collections.clear()

    def create_collection_structure(self, structure: dict, parent_id: Optional[int] = None) -> Dict[str, int]:
        """Create a nested collection structure from a dictionary.
        Returns a mapping of collection names to their IDs."""
        collection_map = {}

        for name, content in structure.items():
            # Create the collection
            collection_id = self.create_collection(name, parent_id)
            collection_map[name] = collection_id

            # Recursively create subcollections if they exist
            if isinstance(content, dict):
                subcollection_map = self.create_collection_structure(content, collection_id)
                collection_map.update(subcollection_map)

        return collection_map
