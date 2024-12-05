import argparse
import json
import sys

from zotero_connector import ZoteroLibrary
from library_organizer import LibraryOrganizer


def load_config(config_path: str = 'config.json') -> dict:
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in config file {config_path}")
        sys.exit(1)


def generate_keywords(library: ZoteroLibrary, organizer: LibraryOrganizer) -> None:
    """Generate new keywords for papers without collections."""
    unclassified = {pid: paper for pid, paper in library.items.items() if not paper.collections}
    print(f"Found {len(unclassified)} unclassified papers")

    for paper_id, paper in unclassified.items():
        print(f"\nProcessing: {paper.title}")
        print(f"Original keywords: {', '.join(paper.keywords)}")
        new_keywords = organizer.improve_paper_keywords(paper_id, library)
        print(f"New keywords: {', '.join(new_keywords)}")


def propose_collections(library: ZoteroLibrary, organizer: LibraryOrganizer, output_path: str = "proposed_collections.json") -> None:
    """Generate and save a proposed collection structure."""
    keywords = library.get_all_keywords()
    print(f"Analyzing {len(keywords)} unique keywords")

    structure = organizer.propose_collection_structure(library)
    organizer.save_proposal(structure, output_path)
    print(f"Saved collection proposal to {output_path}")


def implement_collections(library: ZoteroLibrary, organizer: LibraryOrganizer, structure_path: str) -> None:
    """Implement collection structure from JSON file."""
    try:
        with open(structure_path, 'r') as f:
            structure = json.load(f)
        organizer.implement_collection_structure(structure, library)
        print("Successfully implemented new collection structure")
    except FileNotFoundError:
        print(f"Error: Structure file not found at {structure_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in structure file {structure_path}")
        sys.exit(1)


def classify_papers(library: ZoteroLibrary, organizer: LibraryOrganizer) -> None:
    """Classify papers without collections into the current hierarchy."""
    unclassified = {pid: paper for pid, paper in library.items.items() if not paper.collections}
    print(f"Found {len(unclassified)} unclassified papers")

    for paper_id, paper in unclassified.items():
        print(f"\nProcessing: {paper.title}")
        organizer.classify_paper_in_collections(paper_id, library)
        print(f"Classified into: {', '.join(library.items[paper_id].collections)}")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zotero Library Organization Tool")
    parser.add_argument("--config", default="config.json", help="Path to config file")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Keywords generation
    subparsers.add_parser("keywords", help="Generate keywords for unclassified papers")

    # Collection proposal
    propose_parser = subparsers.add_parser("propose", help="Generate collection structure proposal")
    propose_parser.add_argument("--output", default="proposed_collections.json", help="Output path for proposal JSON")

    # Implement collections
    implement_parser = subparsers.add_parser("implement", help="Implement collection structure from JSON")
    implement_parser.add_argument("structure", help="Path to collection structure JSON")

    # Classify papers
    subparsers.add_parser("classify", help="Classify unclassified papers into collections")
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)
    library = ZoteroLibrary(config['zotero_db_path'])
    library.load_library()
    organizer = LibraryOrganizer(config)

    commands = {
        "keywords": lambda: generate_keywords(library, organizer),
        "propose": lambda: propose_collections(library, organizer, args.output),
        "implement": lambda: implement_collections(library, organizer, args.structure),
        "classify": lambda: classify_papers(library, organizer)
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
