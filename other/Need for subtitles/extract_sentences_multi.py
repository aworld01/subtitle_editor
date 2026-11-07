"""
Extract English-Hindi sentence pairs from MULTIPLE text files into a
single combined dictionary.

Expected format in each file: sentences alternate as
    English sentence
    Hindi sentence
    <blank line>
    English sentence
    Hindi sentence
    <blank line>
    ...

Usage:
    python3 extract_sentences_multi.py file1.txt file2.txt file3.txt -o output.json

    Or use a wildcard (the shell expands this for you):
    python3 extract_sentences_multi.py *.txt -o output.json
"""

import json
import sys
import argparse
import glob
import os

# ---------------------------------------------------------------
# Set your default input directory here.
# When you run the script with no arguments, every .txt file in
# this folder is used automatically.
# ---------------------------------------------------------------
DEFAULT_INPUT_DIR = "."


def extract_pairs_from_file(input_path):
    """Read a single file and return (dict, skipped_lines) for it."""
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
    """Load a previously saved dictionary, if it exists. Returns {} if not."""
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def extract_pairs_from_files(input_paths, existing=None):
    """Merge English-Hindi pairs from multiple files into one dictionary.

    'existing' (if given) is a dict of sentences already saved from a
    previous run — these count as already-seen too, so re-running the
    script only adds genuinely NEW sentences.

    If an English sentence has already been seen (in 'existing', in this
    file, or an earlier file in this run), it is SKIPPED. Everything that
    was NOT already seen is collected into 'new_entries'.
    """
    combined = dict(existing) if existing else {}
    new_entries = {}  # only the sentences added in THIS run
    total_skipped = []
    duplicate_count = 0

    for path in input_paths:
        pairs, skipped = extract_pairs_from_file(path)

        for english, hindi in pairs.items():
            if english in combined:
                duplicate_count += 1
            else:
                combined[english] = hindi
                new_entries[english] = hindi

        total_skipped.extend(skipped)
        print(f"  {path}: {len(pairs)} pairs found")

    return combined, total_skipped, new_entries, duplicate_count


def main():
    parser = argparse.ArgumentParser(
        description="Combine English-Hindi sentence pairs from multiple files into one dictionary."
    )
    parser.add_argument(
        "input_files", nargs="*",
        help=f"Input .txt file(s). If omitted, all .txt files in DEFAULT_INPUT_DIR ({DEFAULT_INPUT_DIR!r}) are used."
    )
    parser.add_argument(
        "-o", "--output", default="combined_sentence_dict.json",
        help="Output JSON file for the combined dictionary (default: combined_sentence_dict.json)"
    )
    parser.add_argument(
        "-n", "--new-entries-output", default="new_entries.json",
        help="Output JSON file for entries added in this run (default: new_entries.json)"
    )
    args = parser.parse_args()

    # If no file paths were given on the command line, scan DEFAULT_INPUT_DIR
    # (set at the top of this script) for .txt files.
    if not args.input_files:
        args.input_files = sorted(glob.glob(os.path.join(DEFAULT_INPUT_DIR, "*.txt")))
        if not args.input_files:
            print(f"No file paths given, and no .txt files found in '{DEFAULT_INPUT_DIR}/'.")
            print(f"Either pass file paths directly, or put .txt files in '{DEFAULT_INPUT_DIR}/'.")
            sys.exit(1)
        print(f"No file paths given — using {len(args.input_files)} file(s) from '{DEFAULT_INPUT_DIR}/':")
        for f in args.input_files:
            print(f"  {f}")

    existing = load_existing_dict(args.output)
    if existing:
        print(f"Loaded {len(existing)} existing pair(s) from {args.output}")

    print(f"Processing {len(args.input_files)} file(s)...")
    combined, skipped, new_entries, duplicate_count = extract_pairs_from_files(
        args.input_files, existing=existing
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    with open(args.new_entries_output, "w", encoding="utf-8") as f:
        json.dump(new_entries, f, ensure_ascii=False, indent=2)

    print(f"\nNew pairs added: {len(new_entries)}")
    print(f"Total pairs in {args.output}: {len(combined)}")
    print(f"Duplicate English sentences found (skipped): {duplicate_count}")
    if new_entries:
        print(f"New entries saved to {args.new_entries_output}")
    if skipped:
        print(f"Warning: {len(skipped)} unpaired line(s) skipped: {skipped}")
    print(f"Saved combined dictionary to {args.output}")


if __name__ == "__main__":
    main()
