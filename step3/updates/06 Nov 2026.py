import json
import sys
import argparse
import glob
import os

DEFAULT_INPUT_DIR = "."

def extract_pairs_from_file(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f]

    non_empty_lines = [line for line in lines if line]

    pairs = {}
    for i in range(0, len(non_empty_lines) - 1, 2):
        english = non_empty_lines[i]
        hindi = non_empty_lines[i + 1]
        pairs[english] = hindi

    skipped = []
    if len(non_empty_lines) % 2 != 0:
        skipped.append(non_empty_lines[-1])

    return pairs, skipped


def load_existing_dict(output_path):
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def clean_and_update_txt_files(txt_files):
    seen_english = set()
    incomplete_report = []

    print("Cleaning and deduplicating text files (preserving formatting)...")
    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            # Read lines while keeping track of raw text
            lines = [line.rstrip("\r\n") for line in f]

        # Extract non-empty lines for checking pairs
        non_empty_pairs = []
        i = 0
        removed_count = 0
        
        # We'll parse block-by-block maintaining original spacing structure
        # Let's rebuild the file content cleanly
        new_file_lines = []
        
        # Filter out empty lines to look at text content sequentially
        non_empty = [l.strip() for l in lines if l.strip()]
        
        idx = 0
        file_valid_pairs = []
        file_incomplete = None
        
        while idx < len(non_empty):
            if idx + 1 < len(non_empty):
                eng = non_empty[idx]
                hin = non_empty[idx+1]
                if eng in seen_english:
                    removed_count += 1
                else:
                    seen_english.add(eng)
                    file_valid_pairs.append((eng, hin))
                idx += 2
            else:
                file_incomplete = non_empty[idx]
                idx += 1

        # Reconstruct file content with blank lines between pairs
        for eng, hin in file_valid_pairs:
            new_file_lines.append(eng)
            new_file_lines.append(hin)
            new_file_lines.append("") # Blank line separator

        if file_incomplete:
            new_file_lines.append(file_incomplete)
            incomplete_report.append((file_path, file_incomplete))

        # Overwrite the text file with formatted lines
        with open(file_path, "w", encoding="utf-8") as f:
            for line in new_file_lines:
                f.write(line + "\n")

        print(f"  {file_path}: Removed {removed_count} duplicate(s)")

    if incomplete_report:
        print("\n--- Incomplete / Unpaired Lines Found ---")
        for f_path, inc_line in incomplete_report:
            print(f"  [File: {f_path}] -> \"{inc_line}\"")
    else:
        print("\nNo incomplete lines found.")


def main():
    parser = argparse.ArgumentParser(
        description="Clean text files, remove duplicates preserving formatting, and build sentence JSON dictionary."
    )
    parser.add_argument(
        "input_files", nargs="*",
        help=f"Input .txt file(s). If omitted, all .txt files in DEFAULT_INPUT_DIR ({DEFAULT_INPUT_DIR!r}) are used."
    )
    parser.add_argument(
        "-o", "--output", default="sentence_dict.json",
        help="Output JSON file for the combined dictionary (default: sentence_dict.json)"
    )
    parser.add_argument(
        "-n", "--new-entries-output", default="new_entries.json",
        help="Output JSON file for entries added in this run (default: new_entries.json)"
    )
    args = parser.parse_args()

    if not args.input_files:
        args.input_files = sorted(glob.glob(os.path.join(DEFAULT_INPUT_DIR, "*.txt")))
        if not args.input_files:
            print(f"No file paths given, and no .txt files found in '{DEFAULT_INPUT_DIR}/'.")
            sys.exit(1)

    # Step 1: Clean text files (remove duplicates, report incomplete lines, keep formatting)
    clean_and_update_txt_files(args.input_files)

    # Step 2: Build/Update JSON Dictionaries
    existing = load_existing_dict(args.output)
    combined = dict(existing)
    new_entries = {}
    total_skipped = []
    duplicate_count = 0

    for path in args.input_files:
        pairs, skipped = extract_pairs_from_file(path)
        for english, hindi in pairs.items():
            if english in combined:
                duplicate_count += 1
            else:
                combined[english] = hindi
                new_entries[english] = hindi
        total_skipped.extend(skipped)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    with open(args.new_entries_output, "w", encoding="utf-8") as f:
        json.dump(new_entries, f, ensure_ascii=False, indent=2)

    print(f"\n--- JSON Summary ---")
    print(f"New pairs added: {len(new_entries)}")
    print(f"Total pairs in {args.output}: {len(combined)}")
    print(f"Saved combined dictionary to {args.output}")

if __name__ == "__main__":
    main()
