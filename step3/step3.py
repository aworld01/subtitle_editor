import json
import sys
import argparse
import glob
import os
import re
import shutil

DEFAULT_INPUT_DIR = "."
UNPAIRED_FILENAME = "unpaired.txt"

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
    """Create a .bak copy if one doesn't already exist."""
    backup = file_path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(file_path, backup)
        return True
    return False


def clean_and_update_txt_files(txt_files):
    """Clean each file independently. Returns count of unpaired sentences."""
    incomplete_report = []

    print("Cleaning and deduplicating text files (preserving formatting)...")

    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f]

        non_empty = [l.strip() for l in lines if l.strip()]

        # --- Smart pairing (handles misaligned files) ---
        raw_pairs, unpaired = smart_pair(non_empty)

        # --- Per-file dedup (does NOT cannibalize other files) ---
        seen_english = set()
        file_valid_pairs = []
        removed_count = 0

        for eng, hin in raw_pairs:
            if eng in seen_english:
                removed_count += 1
            else:
                seen_english.add(eng)
                file_valid_pairs.append((eng, hin))

        # --- Backup original before rewriting ---
        made_backup = backup_file(file_path)

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

        backup_note = " (backup: .bak)" if made_backup else ""
        print(
            f"  {file_path}: {len(file_valid_pairs)} pair(s), "
            f"removed {removed_count} duplicate(s), "
            f"{len(unpaired)} unpaired{backup_note}"
        )

    # --- Write unpaired.txt only if there is something to write ---
    unpaired_lines = [inc_line for _, inc_line in incomplete_report]

    if unpaired_lines:
        with open(UNPAIRED_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n\n".join(unpaired_lines))
            f.write("\n")
        print(f"Unpaired sentences saved to: {UNPAIRED_FILENAME} ({len(unpaired_lines)})")
    else:
        print("No unpaired sentences found. Skipping unpaired.txt.")

    return len(unpaired_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Clean text files, remove duplicates, and build sentence JSON dictionary."
    )
    parser.add_argument(
        "input_files", nargs="*",
        help=f"Input .txt file(s). If omitted, all .txt files in DEFAULT_INPUT_DIR ({DEFAULT_INPUT_DIR!r}) are used."
    )
    parser.add_argument(
        "-o", "--output", default="sentence_dict.json",
        help="Output JSON file for the combined dictionary (default: sentence_dict.json)"
    )
    args = parser.parse_args()

    if not args.input_files:
        args.input_files = sorted(glob.glob(os.path.join(DEFAULT_INPUT_DIR, "*.txt")))
        args.input_files = [
            f for f in args.input_files
            if os.path.basename(f) != UNPAIRED_FILENAME
            and not os.path.basename(f).endswith(".bak")
        ]
        if not args.input_files:
            print(f"No file paths given, and no .txt files found in '{DEFAULT_INPUT_DIR}/'.")
            sys.exit(1)

    # Step 1: Clean text files + write unpaired.txt (if any)
    unpaired_count = clean_and_update_txt_files(args.input_files)

    # Step 2: Build/Update JSON dictionary
    existing = load_existing_dict(args.output)
    combined = dict(existing)
    duplicate_count = 0
    new_count = 0

    for path in args.input_files:
        pairs, _ = extract_pairs_from_file(path)
        for english, hindi in pairs.items():
            if english in combined:
                duplicate_count += 1
            else:
                combined[english] = hindi
                new_count += 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"\n--- JSON Summary ---")
    print(f"Total pairs in {args.output}: {len(combined)}")
    print(f"New pairs added this run:     {new_count}")
    print(f"Duplicate pairs skipped:      {duplicate_count}")
    print(f"Unpaired sentences:           {unpaired_count}")
    print(f"Saved combined dictionary to {args.output}")


if __name__ == "__main__":
    main()