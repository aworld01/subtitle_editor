#!/usr/bin/env python3
"""
Partial dictionary-based SRT translator.

Features
--------
* Deterministic, ambiguity-safe file discovery (CLI overrides accepted).
* Sentence grouping across Latin / Devanagari / Arabic / CJK terminators,
  with abbreviation awareness (Mr., Dr., Ph.D., U.S., e.g., ...).
* Boundary-safe, case-insensitive, punctuation-flexible phrase matching
  (longest key wins, one substitution pass — no chained re-substitution).
* Source trailing punctuation wins over dictionary trailing punctuation.
* A sentence-ending "." is converted to the Hindi danda "।", but ONLY
  when the "." is not part of an abbreviation or decimal number.
* Strong terminators ("!" / "?") suppress a redundant "." so you never
  get "!।" or "?।"; repeated strong terminators ("??", "!!") collapse to
  one so you never get "??" either.
* "Translated" is decided by a configurable coverage threshold.
* Writes `untranslated.txt` (unique, first-seen order) + console stats.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENTENCE_ENDERS = '.?!。？！।؟۔｡…'
TRAILING_PUNCT = '.,?!;:।؟۔…。？！｡'
DANDA = '।'

DEFAULT_PREFIX = 'hindi_'
DEFAULT_UNTRANSLATED = 'untranslated.txt'
DEFAULT_COVERAGE = 0.5

_SEP_CLASS = '[^\\w' + SENTENCE_ENDERS + ']+'

_WORD_RE = re.compile(r'\w+')
_TRAILING_RE = re.compile(r'([ \t]*)(' + re.escape(TRAILING_PUNCT) + r'*)')
_STRIP_TRAILING_RE = re.compile(r'[' + re.escape(TRAILING_PUNCT) + r']+$')

# Cleanup patterns (applied as a final safety net).
_DUP_DANDA_AFTER_STRONG = re.compile(r'([!?])' + re.escape(DANDA) + r'+')
_DUP_DANDA              = re.compile(re.escape(DANDA) + r'{2,}')
_PERIOD_BEFORE_DANDA    = re.compile(r'\.' + re.escape(DANDA))
_DUP_STRONG             = re.compile(r'([!?])\1+')

# ---------------------------------------------------------------------------
# Abbreviations — a "." here is NOT a sentence ender.
# ---------------------------------------------------------------------------
_ABBREVIATIONS = frozenset({
    'mr', 'mrs', 'ms', 'miss', 'mx', 'messrs', 'mme', 'mlle',
    'dr', 'prof', 'rev', 'fr', 'br', 'sr', 'jr', 'st', 'mt', 'ft',
    'gen', 'col', 'capt', 'cmdr', 'lt', 'sgt', 'maj', 'adm', 'cpl',
    'pvt', 'ens', 'ltc',
    'gov', 'sen', 'rep', 'pres', 'amb', 'hon', 'supt', 'insp', 'det',
    'phd', 'md', 'ba', 'ma', 'bs', 'msn', 'llb', 'lld',
    'vs', 'etc', 'cf', 'al', 'approx', 'ca',
    'fig', 'figs', 'eq', 'eqs', 'ref', 'refs', 'ch', 'chs',
    'sec', 'secs', 'vol', 'vols', 'pp',
    'ed', 'eds', 'trans', 'op',
    'inc', 'ltd', 'co', 'corp', 'bros', 'assn', 'dept', 'univ',
    'ave', 'blvd', 'rd', 'ln', 'ct', 'pl', 'sq',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept',
    'oct', 'nov', 'dec',
    'mon', 'tue', 'tues', 'wed', 'thu', 'thur', 'thurs', 'fri',
    'sat', 'sun',
    'ad', 'bc', 'bce', 'ce',
})

_DECIMAL_RE = re.compile(r'\d+(?:\.\d+)+$')
_LETTERS_THAT_ARE_WORDS = frozenset({'A', 'I'})


def _is_abbreviation_period(text, pos):
    if pos <= 0 or pos >= len(text) or text[pos] != '.':
        return False
    i = pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in '.&'):
        i -= 1
    word = text[i + 1:pos]
    if not word:
        return False
    if _DECIMAL_RE.fullmatch(word):
        return False
    if '.' in word:
        return True
    if (len(word) == 1 and word.isupper()
            and word not in _LETTERS_THAT_ARE_WORDS):
        return True
    if word.lower() in _ABBREVIATIONS:
        return True
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description='Partially translate an SRT file using a JSON phrase dictionary.'
    )
    p.add_argument('-i', '--input', help='input .srt file')
    p.add_argument('-d', '--dictionary', help='dictionary .json file')
    p.add_argument('-o', '--output', help='output .srt file')
    p.add_argument('--untranslated', default=DEFAULT_UNTRANSLATED,
                   help='file to write untranslated sentences to')
    p.add_argument('--coverage', type=float, default=DEFAULT_COVERAGE,
                   help='min fraction of source chars replaced to count as '
                        f'translated (default {DEFAULT_COVERAGE})')
    p.add_argument('--prefix', default=DEFAULT_PREFIX,
                   help='output filename prefix; also excluded from input search')
    return p.parse_args()


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def _resolve_explicit(path_str, label):
    p = Path(path_str)
    if not p.exists():
        sys.exit(f'error: {label} not found: {path_str}')
    return p


def pick_srt_file(explicit, prefix, output_name):
    if explicit:
        return _resolve_explicit(explicit, 'input file')
    all_srts = sorted(Path('.').glob('*.srt'))
    if not all_srts:
        sys.exit('error: no .srt files found in the current directory.')
    if output_name:
        all_srts = [f for f in all_srts if f.name != output_name]
    non_prefixed = [f for f in all_srts if not f.name.startswith(prefix)]
    if len(non_prefixed) == 1:
        return non_prefixed[0]
    if len(non_prefixed) > 1:
        names = ', '.join(f.name for f in non_prefixed)
        sys.exit(f'error: ambiguous input; multiple non-prefixed .srt files: '
                 f'{names}. Use --input to pick one.')
    if len(all_srts) == 1:
        print(f'warning: no non-prefixed .srt found; using {all_srts[0].name}',
              file=sys.stderr)
        return all_srts[0]
    sys.exit('error: no usable .srt files remain after exclusions. Use --input.')


def pick_dict_file(explicit):
    if explicit:
        return _resolve_explicit(explicit, 'dictionary file')
    jsons = sorted(Path('.').glob('*.json'))
    if not jsons:
        sys.exit('error: no .json dictionary found.')
    if len(jsons) > 1:
        names = ', '.join(f.name for f in jsons)
        sys.exit(f'error: ambiguous dictionary; multiple .json files: {names}. '
                 f'Use --dictionary.')
    return jsons[0]


# ---------------------------------------------------------------------------
# SRT parsing
# ---------------------------------------------------------------------------
def parse_srt(content):
    blocks = []
    for raw in re.split(r'\n\s*\n', content.strip()):
        lines = raw.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'\s*([\d:,]+)\s*-->\s*([\d:,]+)', lines[1])
        if not m:
            continue
        blocks.append({'start': m.group(1), 'end': m.group(2),
                       'text': ' '.join(lines[2:])})
    return blocks


def _ends_sentence(text):
    s = text.rstrip()
    if not s:
        return False
    last = s[-1]
    if last not in SENTENCE_ENDERS:
        return False
    if last == '.' and _is_abbreviation_period(s, len(s) - 1):
        return False
    return True


def group_into_sentences(blocks):
    groups, cur_times, cur_parts = [], None, []
    for i, block in enumerate(blocks):
        if cur_times is None:
            cur_times = [block['start'], block['end']]
        else:
            cur_times[1] = block['end']
        cur_parts.append(block['text'])
        combined = re.sub(r'\s+', ' ', ' '.join(cur_parts)).strip()
        if _ends_sentence(combined) or i == len(blocks) - 1:
            groups.append({'start': cur_times[0], 'end': cur_times[1],
                           'text': combined})
            cur_times, cur_parts = None, []
    return groups


# ---------------------------------------------------------------------------
# Flexible matching
# ---------------------------------------------------------------------------
def key_to_regex(key):
    tokens = _WORD_RE.findall(key)
    if not tokens:
        return None
    if len(tokens) == 1:
        return r'\b' + re.escape(tokens[0]) + r'\b'
    parts = [re.escape(t) for t in tokens]
    return r'\b' + _SEP_CLASS.join(parts) + r'\b'


def build_combined_pattern(keys):
    ordered = sorted(keys, key=len, reverse=True)
    parts, group_to_key = [], {}
    for i, key in enumerate(ordered):
        frag = key_to_regex(key)
        if frag is None:
            continue
        gname = f'k{i}'
        group_to_key[gname] = key
        parts.append(f'(?P<{gname}>{frag})')
    if not parts:
        return None, group_to_key
    return re.compile('|'.join(parts), re.IGNORECASE), group_to_key


def extract_trailing_punct(text, end_pos):
    m = _TRAILING_RE.match(text, end_pos)
    if not m:
        return '', ''
    return m.group(1), m.group(2)


# --- FIXED: strong terminators deduplicated; "." → danda handled ---
def attach_source_punct(translation, source_punct):
    """
    Attach the source's trailing punctuation to a dictionary translation.

    Rules (in order):
      1. Source has "!" or "?"  → keep unique strong chars in order.
                                    "??" → "?",  "!!" → "!",  "?!" → "?!"
      2. Source has "।"         → keep one danda.
      3. Source has "." only    → "।" (but "..." stays "...").
      4. Source has "," ";" ":" → keep literally.
      5. No source punctuation  → leave the dictionary's own punctuation.
    """
    if not source_punct:
        return translation

    stripped = _STRIP_TRAILING_RE.sub('', translation)

    # 1. Strong terminators win.  Dedupe (keep first occurrence of each).
    seen = []
    for c in source_punct:
        if c in '!?' and c not in seen:
            seen.append(c)
    if seen:
        return stripped + ''.join(seen)

    # 2. Danda already present.
    if DANDA in source_punct:
        return stripped + DANDA

    # 3. Period / ellipsis.
    if '.' in source_punct:
        if set(source_punct) == {'.'} and len(source_punct) > 1:
            return stripped + source_punct
        return stripped + DANDA

    # 4. Comma / semicolon / colon etc.
    return stripped + source_punct


# --- FIXED: strong-terminator dedup added ---
def cleanup_terminators(text):
    """Collapse accidental consecutive terminators anywhere in the text."""
    text = _DUP_DANDA_AFTER_STRONG.sub(r'\1', text)   # "!।" / "?।" → "!" / "?"
    text = _DUP_DANDA.sub(DANDA, text)                # "।।" → "।"
    text = _PERIOD_BEFORE_DANDA.sub(DANDA, text)      # ".।" → "।"
    text = _DUP_STRONG.sub(r'\1', text)               # "??" → "?", "!!" → "!"
    return text


def translate_sentence(text, pattern, group_to_key, trans_dict):
    if pattern is None:
        return text, 0

    pieces, cursor, matched = [], 0, 0
    for m in pattern.finditer(text):
        gname = m.lastgroup
        if gname is None:
            continue
        translation = trans_dict[group_to_key[gname]]
        ws, punct = extract_trailing_punct(text, m.end())
        pieces.append(text[cursor:m.start()])
        pieces.append(attach_source_punct(translation, punct))
        matched += m.end() - m.start()
        cursor = m.end() + len(ws) + len(punct) if punct else m.end()

    pieces.append(text[cursor:])
    new_text = ''.join(pieces)

    if new_text.endswith('.'):
        if not _is_abbreviation_period(new_text, len(new_text) - 1):
            new_text = new_text[:-1] + DANDA

    new_text = cleanup_terminators(new_text)
    return new_text, matched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    if not 0.0 <= args.coverage <= 1.0:
        sys.exit('error: --coverage must be between 0 and 1.')

    input_path = pick_srt_file(args.input, args.prefix, args.output)
    dict_path = pick_dict_file(args.dictionary)
    output_path = Path(args.output) if args.output else \
                  input_path.with_name(f'{args.prefix}{input_path.name}')

    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            trans_dict = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f'error: invalid JSON in {dict_path}: {e}')
    if not trans_dict:
        sys.exit(f'error: dictionary {dict_path} is empty.')
    if not all(isinstance(v, str) for v in trans_dict.values()):
        sys.exit('error: all dictionary values must be strings.')

    with open(input_path, 'r', encoding='utf-8') as f:
        blocks = parse_srt(f.read())
    if not blocks:
        sys.exit(f'error: no valid subtitle blocks parsed from {input_path}.')

    groups = group_into_sentences(blocks)
    pattern, group_to_key = build_combined_pattern(trans_dict.keys())

    sentences, translated_count, untranslated = [], 0, []
    for g in groups:
        new_text, matched = translate_sentence(
            g['text'], pattern, group_to_key, trans_dict
        )
        coverage = matched / max(len(g['text']), 1)
        if coverage >= args.coverage:
            translated_count += 1
        else:
            untranslated.append(g['text'])
        sentences.append({'start': g['start'], 'end': g['end'],
                          'text': new_text, 'coverage': coverage})

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, s in enumerate(sentences, 1):
            f.write(f"{i}\n{s['start']} --> {s['end']}\n{s['text']}\n\n")

    seen, unique = set(), []
    for u in untranslated:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    with open(args.untranslated, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(unique))
        if unique:
            f.write('\n')

    total = len(sentences)
    avg_cov = sum(s['coverage'] for s in sentences) / total if total else 0.0
    print(f'Input:                        {input_path}')
    print(f'Dictionary:                   {dict_path}')
    print(f'Output:                       {output_path}')
    print(f'Total sentences:              {total}')
    print(f'Translated (cov >= {args.coverage:.0%}):  {translated_count}')
    print(f'Unique untranslated sentences:{len(unique)}')
    print(f'Average coverage:             {avg_cov:.1%}')


if __name__ == '__main__':
    main()