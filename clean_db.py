import os
import shutil

def wipe_environment():
    db_file = "depop_data.db"
    storage_dir = "storage"

    print("=== Environment Cleanup ===")

    # 1. Prompt for Database
    db_confirm = input(f"Wipe the SQLite database ({db_file})? (y/n): ").strip().lower()
    if db_confirm == 'y':
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f" [DELETED] {db_file}")
        else:
            print(f" [SKIP] No database found at {db_file}")
    else:
        print(f" [KEPT] {db_file}")

    print("-" * 25)

    # 2. Prompt for Crawlee Storage
    storage_confirm = input(f"Wipe the Crawlee raw storage ({storage_dir}/)? (y/n): ").strip().lower()
    if storage_confirm == 'y':
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir)
            print(f" [DELETED] {storage_dir}/")
        else:
            print(f" [SKIP] No storage directory found at {storage_dir}/")
    else:
        print(f" [KEPT] {storage_dir}/")

    print("===========================\nCleanup routine finished.")

    # Create prompt for wiping database records only, without touching the storage directory

if __name__ == "__main__":
    wipe_environment()