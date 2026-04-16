import os
import shutil

# ─────────────────────────────────────────────
#  CONFIGURATION — edit this to your liking
# ─────────────────────────────────────────────

# The folder you want to organize.
# Change this to any folder path on your machine.
# Example: "/home/cody/Downloads"
FOLDER_TO_ORGANIZE = "/home/cody/Downloads"

# If True, prints every action but moves NOTHING.
# Great for testing before you commit.
DRY_RUN = False

# ─────────────────────────────────────────────
#  FILE TYPE DEFINITIONS
#  Format: "Subfolder Name": [".ext1", ".ext2"]
# ─────────────────────────────────────────────

FILE_TYPES = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".tiff", ".tif", ".webp", ".svg", ".ico",
        ".heic", ".heif", ".raw", ".cr2", ".nef"
    ],
    "Videos": [
        ".mp4", ".mkv", ".avi", ".mov", ".wmv",
        ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
        ".3gp", ".ts", ".vob"
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".aac", ".ogg",
        ".wma", ".m4a", ".opus", ".aiff", ".mid",
        ".midi"
    ],
    "Documents": [
        ".pdf", ".docx", ".doc", ".txt", ".rtf",
        ".odt", ".pages", ".tex", ".md", ".epub",
        ".mobi"
    ],
    "Spreadsheets": [
        ".xlsx", ".xls", ".csv", ".ods", ".numbers"
    ],
    "Presentations": [
        ".pptx", ".ppt", ".odp", ".key"
    ],
    "Code": [
        ".py", ".js", ".ts", ".html", ".css",
        ".java", ".cpp", ".c", ".h", ".cs",
        ".php", ".rb", ".go", ".rs", ".swift",
        ".sh", ".bat", ".ps1", ".r", ".sql",
        ".json", ".xml", ".yaml", ".yml", ".toml",
        ".ini", ".cfg", ".env"
    ],
    "Archives": [
        ".zip", ".7z", ".rar", ".tar", ".gz",
        ".bz2", ".xz", ".tar.gz", ".tar.bz2",
        ".tar.xz", ".tgz", ".iso", ".img", ".dmg"
    ],
    "Executables": [
        ".exe", ".msi", ".apk", ".deb", ".rpm",
        ".appimage", ".run"
    ],
    "Torrents": [
        ".torrent", ".magnet"
    ],
    "Databases": [
        ".kdbx", ".kdb", ".db", ".sqlite",
        ".sqlite3", ".sql", ".mdb", ".accdb"
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2", ".eot"
    ],
    "3D_and_Design": [
        ".psd", ".ai", ".xd", ".fig", ".sketch",
        ".blend", ".obj", ".fbx", ".stl", ".dae"
    ],
    "Ebooks": [
        ".epub", ".mobi", ".azw", ".azw3", ".cbr", ".cbz"
    ],
}

# ─────────────────────────────────────────────
#  CORE FUNCTIONS
# ─────────────────────────────────────────────

def get_file_category(filename):
    """
    Checks a filename's extension against FILE_TYPES
    and returns the matching category name.
    Returns None if no match is found.
    """
    # Pull the extension off the filename and lowercase it
    # so .JPG and .jpg are treated the same
    extension = os.path.splitext(filename)[1].lower()

    for category, extensions in FILE_TYPES.items():
        if extension in extensions:
            return category

    return None  # No category found


def create_subfolders(base_folder):
    """
    Creates a subfolder for each category inside the target folder,
    but only if the subfolder doesn't already exist.
    """
    for category in FILE_TYPES:
        subfolder_path = os.path.join(base_folder, category)
        if not os.path.exists(subfolder_path):
            if not DRY_RUN:
                os.makedirs(subfolder_path)
            print(f"  [+] Created folder: {category}")


def move_file(filename, source_folder, category):
    """
    Moves a single file into its category subfolder.
    Handles filename conflicts by adding a number to the end.
    """
    source_path = os.path.join(source_folder, filename)
    destination_folder = os.path.join(source_folder, category)
    destination_path = os.path.join(destination_folder, filename)

    # If a file with the same name already exists in the destination,
    # add a number to avoid overwriting it: photo(1).jpg, photo(2).jpg etc.
    if os.path.exists(destination_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(destination_path):
            new_filename = f"{base}({counter}){ext}"
            destination_path = os.path.join(destination_folder, new_filename)
            counter += 1

    if not DRY_RUN:
        shutil.move(source_path, destination_path)

    print(f"  [→] {filename}  →  {category}/")


def organize_folder(folder_path):
    """
    Main function. Scans the target folder and moves each file
    into the correct subfolder based on its extension.
    """
    # Make sure the folder actually exists before we do anything
    if not os.path.exists(folder_path):
        print(f"\n  [ERROR] Folder not found: {folder_path}")
        print("  Double-check the FOLDER_TO_ORGANIZE path at the top of this script.")
        return

    print("\n" + "─" * 50)
    print("  THE FOLDER ORGANIZER")
    if DRY_RUN:
        print("  *** DRY RUN MODE — no files will be moved ***")
    print(f"  Target: {folder_path}")
    print("─" * 50)

    # Step 1: Create all the subfolders
    print("\n[1] Creating subfolders...")
    create_subfolders(folder_path)

    # Step 2: Loop through every item in the folder
    print("\n[2] Sorting files...")

    moved = 0
    skipped = 0
    unknown = 0

    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)

        # Skip subfolders — we only want to move files
        if os.path.isdir(item_path):
            continue

        # Figure out which category this file belongs to
        category = get_file_category(item)

        if category is None:
            print(f"  [?] {item}  →  Unknown type, skipping")
            unknown += 1
            continue

        # Don't move a file if it's already in the right place
        # (this prevents re-running the script from causing issues)
        if os.path.basename(os.path.dirname(item_path)) == category:
            skipped += 1
            continue

        move_file(item, folder_path, category)
        moved += 1

    # Step 3: Print a summary
    print("\n" + "─" * 50)
    print("  DONE.")
    print(f"  Files moved:   {moved}")
    print(f"  Unknown types: {unknown}")
    print(f"  Skipped:       {skipped}")
    print("─" * 50 + "\n")


# ─────────────────────────────────────────────
#  RUN IT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    organize_folder(FOLDER_TO_ORGANIZE)
