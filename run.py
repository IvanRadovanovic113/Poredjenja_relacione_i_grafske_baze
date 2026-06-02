#!/usr/bin/env python3
"""
Orchestrates data generation and loading into PostgreSQL and/or Neo4j.

Usage:
    python run.py --scale 150
    python run.py --scale 15000
    python run.py --scale 100000
    python run.py --scale 15000 --target pg
    python run.py --scale 15000 --target neo4j
    python run.py --scale 15000 --skip-generate   # reuse previously generated data
"""
import argparse
import os
import subprocess
import sys
import time


def run(script, extra_args):
    cmd = [sys.executable, script] + extra_args
    label = ' '.join(cmd)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    t0 = time.perf_counter()
    result = subprocess.run(cmd)
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        print(f"\nFAILED: {script} exited with code {result.returncode}")
        sys.exit(result.returncode)
    return elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', type=int, default=15000,
                        help='Number of transactions: 150 | 15000 | 100000')
    parser.add_argument('--target', choices=['both', 'pg', 'neo4j'], default='both')
    parser.add_argument('--skip-generate', action='store_true',
                        help='Skip generation if data/<scale>/ already exists')
    args = parser.parse_args()

    times = {}

    data_dir = os.path.join('data', str(args.scale))
    if args.skip_generate and os.path.isdir(data_dir):
        print(f"Skipping generation — data already exists at {data_dir}")
    else:
        t = run('generate.py', ['--scale', str(args.scale)])
        times['generate'] = t

    if args.target in ('both', 'pg'):
        t = run(os.path.join('postgresql', 'load.py'), ['--scale', str(args.scale)])
        times['postgresql'] = t

    if args.target in ('both', 'neo4j'):
        t = run(os.path.join('neo4j', 'load.py'), ['--scale', str(args.scale)])
        times['neo4j'] = t

    print(f"\n{'='*60}")
    print(f"  Summary  (scale={args.scale})")
    print(f"{'='*60}")
    for step, sec in times.items():
        print(f"  {step:<20} {sec:>7.2f}s")


if __name__ == '__main__':
    main()
