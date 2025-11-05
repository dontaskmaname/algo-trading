import argparse
from src.db.database import get_session, ManualLevel

def list_levels():
    """Lists all manual levels."""
    session = get_session()
    levels = session.query(ManualLevel).all()
    session.close()
    if not levels:
        print("No manual levels found.")
        return
    for level in levels:
        print(f"ID: {level.id}, Type: {level.level_type}, Price: {level.price}")

def add_level(level_type: str, price: float):
    """Adds a new manual level."""
    session = get_session()
    new_level = ManualLevel(level_type=level_type, price=price)
    session.add(new_level)
    session.commit()
    print(f"Added {level_type} level at {price}")
    session.close()

def delete_level(level_id: int):
    """Deletes a manual level."""
    session = get_session()
    level = session.query(ManualLevel).filter(ManualLevel.id == level_id).first()
    if not level:
        print(f"No level found with ID {level_id}")
        return
    session.delete(level)
    session.commit()
    print(f"Deleted level with ID {level_id}")
    session.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Manage manual support and resistance levels.")
    parser.add_argument('action', choices=['list', 'add', 'delete'], help="The action to perform.")
    parser.add_argument('--type', choices=['support', 'resistance'], help="The type of the level (for 'add' action).")
    parser.add_argument('--price', type=float, help="The price of the level (for 'add' action).")
    parser.add_argument('--id', type=int, help="The ID of the level to delete (for 'delete' action).")

    args = parser.parse_args()

    if args.action == 'list':
        list_levels()
    elif args.action == 'add':
        if not args.type or not args.price:
            print("Please provide both --type and --price for the 'add' action.")
        else:
            add_level(args.type, args.price)
    elif args.action == 'delete':
        if not args.id:
            print("Please provide the --id of the level to delete.")
        else:
            delete_level(args.id)
