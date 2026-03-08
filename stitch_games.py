"""
stitch_games.py  —  Merge individual game_data/*.json files into one benchmark JSON.

Usage:
    python stitch_games.py                        # merge all files in game_data/
    python stitch_games.py game_data/game_4p_*   # glob specific files
    python stitch_games.py -o merged.json         # custom output file
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


def stitch(input_files, output_file):
    files = sorted(input_files)
    if not files:
        print("No input files found.")
        sys.exit(1)

    all_games = []
    config = None

    for path in files:
        with open(path) as f:
            data = json.load(f)
        if config is None:
            config = dict(data['config'])
        for game in data['games']:
            game = dict(game)
            game['game'] = len(all_games) + 1   # renumber sequentially
            all_games.append(game)

    config['games'] = len(all_games)

    merged = {'config': config, 'games': all_games}
    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)
    print(f"Merged {len(all_games)} games from {len(files)} files → {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Merge game_data JSON files into one benchmark JSON.')
    parser.add_argument('files', nargs='*', help='Input JSON files (default: all in game_data/)')
    parser.add_argument('-o', '--output', default=None, help='Output file path')
    args = parser.parse_args()

    if args.files:
        input_files = [Path(f) for f in args.files]
    else:
        game_data_dir = Path(__file__).parent / 'game_data'
        input_files = sorted(game_data_dir.glob('*.json'))

    if args.output:
        output_file = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = Path(__file__).parent / f'benchmark_stitched_{ts}.json'

    stitch(input_files, output_file)


if __name__ == '__main__':
    main()
