import json
import sys
import glob
import os
import re
import shutil

DEFAULT_INPUT_DIR = "."
UNPAIRED_FILENAME = "unpaired.txt"

# Hardcoded output JSON (replaces the old -o/--output argument)
OUTPUT_JSON = "sentence_dict.json"

# Folder where .bak copies of processed files are stored
BACKUP_DIR = "backup"

# Regex to detect Devanagari (Hindi) characters
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
# Regex to detect Latin letters
LATIN_RE = re.compile(r"[A-Za-z]")


def looks_hindi(s):
    """True if string contains any Devanagari characters."""
    return bool(DEVANAGARI_RE.search(s))


def looks_english(s):
    """True if string has Latin letters and NO Devanagari characters."""
    return bool(LATIN_RE.search(s)) and not looks_hindi(s)


def classify_line(s):
    """Return 'en', 'hi', or 'unknown' based on script content."""
    if looks_english(s):
        return "en"
    if looks_hindi(s):
        return "hi"
    return "unknown"


def extract_pairs_from_file(input_path):
    """Parse a (hopefully clean) txt file into {english: hindi}."""
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f]

    non_empty_lines = [line for line in lines if line]

    pairs = {}
    skipped = []
    for i in range(0, len(non_empty_lines) - 1, 2):
        english = non_empty_lines[i]
        hindi = non_empty_lines[i + 1]
        pairs[english] = hindi

    if len(non_empty_lines) % 2 != 0:
        skipped.append(non_empty_lines[-1])

    return pairs, skipped


def load_existing_dict(output_path):
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def smart_pair(non_empty):
    """
    Pair lines using script detection so a missing Hindi line doesn't
    shift every subsequent pair.

    Returns (pairs, unpaired) where:
        pairs    = list of (english, hindi)
        unpaired = list of stray lines (missing a partner)
    """
    pairs = []
    unpaired = []
    i = 0
    n = len(non_empty)

    while i < n - 1:
        a, b = non_empty[i], non_empty[i + 1]
        ca, cb = classify_line(a), classify_line(b)

        if ca == "en" and cb == "hi":
            pairs.append((a, b))
            i += 2

        elif ca == "en" and cb == "en":
            # English followed by English → the first has no Hindi partner
            unpaired.append(a)
            i += 1

        elif ca == "hi" and cb == "hi":
            pairs.append((a, b))
            i += 2

        elif ca == "hi" and cb == "en":
            # Hindi with no English partner
            unpaired.append(a)
            i += 1

        else:
            # "unknown" script (numbers, punctuation, emoji, etc.)
            pairs.append((a, b))
            i += 2

    if i < n:
        unpaired.append(non_empty[i])

    return pairs, unpaired


def backup_file(file_path):
    """
    Copy file into the BACKUP_DIR folder (only once per source file).
    Returns (made_backup, backup_path).
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)

    base = os.path.basename(file_path)
    backup_path = os.path.join(BACKUP_DIR, base + ".bak")

    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        return True, backup_path
    return False, backup_path


def clean_and_update_txt_files(txt_files):
    """Clean each file independently. Returns count of unpaired sentences."""
    incomplete_report = []

    # ---- GLOBAL dedup set: spans ALL input files ----
    # Created once outside the loop so a sentence already seen in an earlier
    # file is removed from every later file too.
    seen_english = set()

    print("Cleaning and deduplicating text files (preserving formatting)...")

    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f]

        non_empty = [l.strip() for l in lines if l.strip()]

        # --- Smart pairing (handles misaligned files) ---
        raw_pairs, unpaired = smart_pair(non_empty)

        # --- GLOBAL dedup (across all files, not just within this one) ---
        file_valid_pairs = []
        removed_count = 0

        for eng, hin in raw_pairs:
            if eng in seen_english:
                removed_count += 1
            else:
                seen_english.add(eng)
                file_valid_pairs.append((eng, hin))

        # --- Backup original before rewriting (into BACKUP_DIR) ---
        made_backup, backup_path = backup_file(file_path)

        # --- Rebuild file with ONLY valid pairs ---
        new_file_lines = []
        for eng, hin in file_valid_pairs:
            new_file_lines.append(eng)
            new_file_lines.append(hin)
            new_file_lines.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            for line in new_file_lines:
                f.write(line + "\n")

        # --- Record unpaired lines for unpaired.txt (NOT written back to source) ---
        for line in unpaired:
            incomplete_report.append((file_path, line))

        backup_note = f" (backup: {backup_path})" if made_backup else ""
        print(
            f"  {file_path}: {len(file_valid_pairs)} pair(s), "
            f"removed {removed_count} duplicate(s), "
            f"{len(unpaired)} unpaired{backup_note}"
        )

    # --- Global dedup of unpaired lines too (case-insensitive) ---
    seen_unpaired = set()
    unpaired_unique = []
    for _, line in incomplete_report:
        key = line.strip().lower()
        if key in seen_unpaired:
            continue
        seen_unpaired.add(key)
        unpaired_unique.append(line)

    # --- Write unpaired.txt only if there is something to write ---
    if unpaired_unique:
        with open(UNPAIRED_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n\n".join(unpaired_unique))
            f.write("\n")
        print(
            f"Unpaired sentences saved to: {UNPAIRED_FILENAME} "
            f"({len(unpaired_unique)} unique, {len(incomplete_report)} total)"
        )
    else:
        print("No unpaired sentences found. Skipping unpaired.txt.")

    return len(unpaired_unique)


def remove_empty_txt_files(txt_files):
    """
    Delete any of the given .txt files that ended up empty after cleaning.
    Never touches unpaired.txt, .bak files, or anything in BACKUP_DIR.
    Returns the list of removed file paths.
    """
    removed = []
    for path in txt_files:
        base = os.path.basename(path)
        if base == UNPAIRED_FILENAME or base.endswith(".bak"):
            continue
        if os.path.dirname(os.path.abspath(path)) == os.path.abspath(BACKUP_DIR):
            continue
        if os.path.isfile(path) and os.path.getsize(path) == 0:
            try:
                os.remove(path)
                removed.append(path)
                print(f"🗑️  Removed empty file: {path}")
            except OSError as e:
                print(f"⚠️  Could not remove {path}: {e}")

    if not removed:
        print("✅ No empty .txt files to remove.")
    return removed


def main():
    # Auto-discover input .txt files in DEFAULT_INPUT_DIR
    input_files = sorted(glob.glob(os.path.join(DEFAULT_INPUT_DIR, "*.txt")))
    input_files = [
        f for f in input_files
        if os.path.basename(f) != UNPAIRED_FILENAME
        and not os.path.basename(f).endswith(".bak")
    ]

    if not input_files:
        print(f"No .txt files found in '{DEFAULT_INPUT_DIR}/'.")
        sys.exit(1)

    # Step 1: Clean text files + write unpaired.txt (if any)
    unpaired_count = clean_and_update_txt_files(input_files)

    # Step 2: Build/Update JSON dictionary
    existing = load_existing_dict(OUTPUT_JSON)
    combined = dict(existing)
    duplicate_count = 0
    new_count = 0

    for path in input_files:
        pairs, _ = extract_pairs_from_file(path)
        for english, hindi in pairs.items():
            if english in combined:
                duplicate_count += 1
            else:
                combined[english] = hindi
                new_count += 1

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"\n--- JSON Summary ---")
    print(f"Total pairs in {OUTPUT_JSON}: {len(combined)}")
    print(f"New pairs added this run:     {new_count}")
    print(f"Duplicate pairs skipped:      {duplicate_count}")
    print(f"Unpaired sentences:           {unpaired_count}")
    print(f"Saved combined dictionary to {OUTPUT_JSON}")

    # Step 3: Remove any source files that ended up empty
    print()
    remove_empty_txt_files(input_files)


if __name__ == "__main__":
    main()