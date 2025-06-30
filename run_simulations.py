#!/usr/bin/env python
"""
Fab Flow Game Mass Simulation Tool

This script runs thousands of simulations of the Fab Flow game to generate
statistically significant data for comparing different strategies.

Usage:
  python run_simulations.py [--simulations=3000] [--output=simulation_results.db]
"""
import os
import sys
import time
import random
import sqlite3
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Import game constants and functions from app.py
# We'll duplicate essential game functions here to avoid dependencies

# --- Game Constants ---
NUM_STEPS = 10
NUM_ROUNDS = 20
RAW_MATERIAL = float('inf')
DICE_RANGE = (1, 6)

class Station:
    def __init__(self, step, wip, fifo=None):
        self.step = step
        self.wip = wip
        self.capacity = 0
        self.throughput = 0
        self.fifo = fifo if fifo is not None else []
        self.output = 0

def initialize_stations(start_wip):
    stations = []
    stations.append(Station(0, RAW_MATERIAL, []))
    for i in range(1, NUM_STEPS):
        fifo = [(f"U{i}-{j}", 0) for j in range(start_wip)]
        stations.append(Station(i, start_wip, fifo))
    return stations

def roll_dice(num_steps, dice_range):
    return [random.randint(*dice_range) for _ in range(num_steps)]

def process_round(stations, prev_incoming, dice_range, round_num, finished_units, finished_cycles, tracked_units):
    dice = roll_dice(NUM_STEPS, dice_range)
    throughputs = []
    new_incoming = [[] for _ in range(NUM_STEPS)]
    round_finished_units = []

    # Track start WIP for each station for this round
    start_wip_per_step = [s.wip if s.wip != RAW_MATERIAL else 999 for s in stations]

    # Step 0 (Raw material)
    stations[0].capacity = dice[0]
    stations[0].throughput = dice[0]
    throughputs.append(stations[0].throughput)

    for unit_tuple in prev_incoming[1]:
        stations[1].fifo.append(unit_tuple)

    for _ in range(stations[0].throughput):
        unit_id = f"U1-{random.randint(10000,99999)}"
        unit_tuple = (unit_id, round_num)
        new_incoming[1].append(unit_tuple)
        tracked_units[unit_id] = {'entry': round_num, 'exit': None}

    for i in range(1, NUM_STEPS):
        if i != 1 and prev_incoming[i]:
            stations[i].fifo.extend(prev_incoming[i])
        # Available to process WIP is current FIFO length
        available_wip = len(stations[i].fifo)
        stations[i].capacity = dice[i]
        stations[i].throughput = min(available_wip, stations[i].capacity)
        throughputs.append(stations[i].throughput)
        moved = [stations[i].fifo.pop(0) for _ in range(stations[i].throughput)]
        if i < NUM_STEPS - 1:
            new_incoming[i+1] = moved
        else:
            for unit_id, entry_round in moved:
                finished_units.append((unit_id, entry_round, round_num + 1))
                round_finished_units.append((unit_id, entry_round, round_num + 1))
                if unit_id in tracked_units and tracked_units[unit_id]['exit'] is None:
                    tracked_units[unit_id]['exit'] = round_num + 1
                if unit_id.startswith("U1-") and entry_round > 0:
                    finished_cycles.append((round_num + 1) - entry_round)

    # Update WIP for each station after all throughputs are calculated
    for i in range(NUM_STEPS):
        if i == 0:
            stations[i].wip = max(0, start_wip_per_step[i] - throughputs[i])
        else:
            stations[i].wip = max(0, start_wip_per_step[i] - throughputs[i] + throughputs[i-1])

    end_wip_per_step = [s.wip if s.wip != RAW_MATERIAL else '∞' for s in stations]
    total_end_wip = sum(s.wip for s in stations[1:])
    
    return (
        new_incoming,
        throughputs,
        dice,
        finished_units,
        finished_cycles,
        end_wip_per_step,
        total_end_wip,
        round_finished_units,
        start_wip_per_step
    )

def get_tracked_avg_cycle_time(tracked_units):
    cycle_times = [v['exit'] - v['entry'] for v in tracked_units.values() if v['exit'] is not None]
    if cycle_times:
        return round(sum(cycle_times) / len(cycle_times), 2)
    return 0.00

def simulate_game(strategy):
    """
    Simulate a complete game with the specified strategy.
    
    Args:
        strategy (str): One of 'A', 'B', 'C' for the different game strategies
        
    Returns:
        dict: Results including total output, end WIP, and average cycle time
    """
    # Configure settings based on strategy
    settings = {
        "A": {"dice_range": (1, 7), "start_wip": 4},  # Increased capacity
        "B": {"dice_range": (2, 5), "start_wip": 4},  # Reduced variability
        "C": {"dice_range": (1, 6), "start_wip": 5},  # Increased WIP
        "original": {"dice_range": (1, 6), "start_wip": 4}  # Original game
    }
    
    config = settings.get(strategy, settings["original"])
    
    # Initialize game state
    stations = initialize_stations(config["start_wip"])
    prev_incoming = [[] for _ in range(NUM_STEPS)]
    finished_units = []
    finished_cycles = []
    tracked_units = {}
    round_outputs = []
    
    # Run all rounds
    for round_num in range(1, NUM_ROUNDS + 1):
        (
            prev_incoming,
            throughputs,
            dice,
            finished_units,
            finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units,
            _  # start_wip_per_step (unused)
        ) = process_round(
            stations,
            prev_incoming,
            config["dice_range"],
            round_num,
            finished_units,
            finished_cycles,
            tracked_units
        )
        
        round_outputs.append(len(round_finished_units))
    
    # Calculate final results
    total_output = sum(round_outputs)
    tracked_avg_cycle_time = get_tracked_avg_cycle_time(tracked_units)
    
    # Return the results
    return {
        "strategy": strategy,
        "total_output": total_output, 
        "end_wip": total_end_wip,
        "avg_cycle_time": tracked_avg_cycle_time,
        "round_outputs": round_outputs,
        "settings": config
    }

def setup_database(db_path):
    """Create a new database for storing simulation results"""
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE simulations (
        id INTEGER PRIMARY KEY,
        strategy TEXT NOT NULL,
        total_output INTEGER NOT NULL,
        end_wip INTEGER NOT NULL,
        avg_cycle_time REAL NOT NULL,
        dice_min INTEGER NOT NULL,
        dice_max INTEGER NOT NULL,
        start_wip INTEGER NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE round_outputs (
        simulation_id INTEGER NOT NULL,
        round_num INTEGER NOT NULL,
        output INTEGER NOT NULL,
        FOREIGN KEY (simulation_id) REFERENCES simulations (id)
    )
    ''')
    
    conn.commit()
    return conn

def run_mass_simulations(num_simulations=3000, db_path='simulation_results.db'):
    """Run a large number of simulations for each strategy"""
    print(f"Starting {num_simulations} simulations per strategy (total: {num_simulations * 4})...")
    
    # Set up the database
    conn = setup_database(db_path)
    cursor = conn.cursor()
    
    strategies = ['original', 'A', 'B', 'C']
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Run simulations for each strategy
    for strategy in strategies:
        print(f"\nRunning {num_simulations} simulations for strategy '{strategy}'...")
        start_time = time.time()
        
        # Create a simple progress indicator
        for i in range(num_simulations):
            if i % 100 == 0:
                progress = i / num_simulations * 100
                elapsed = time.time() - start_time
                est_total = elapsed / (i + 1) * num_simulations if i > 0 else 0
                remaining = est_total - elapsed
                sys.stdout.write(f"\rProgress: {progress:.1f}% | Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s | Simulations: {i}/{num_simulations}")
                sys.stdout.flush()
                
            # Run a single simulation
            result = simulate_game(strategy)
            
            # Insert the main results into the database
            cursor.execute(
                '''
                INSERT INTO simulations 
                (strategy, total_output, end_wip, avg_cycle_time, 
                 dice_min, dice_max, start_wip, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', 
                (
                    strategy, 
                    result['total_output'], 
                    result['end_wip'], 
                    result['avg_cycle_time'],
                    result['settings']['dice_range'][0],
                    result['settings']['dice_range'][1],
                    result['settings']['start_wip'],
                    timestamp
                )
            )
            
            # Get the ID of the inserted simulation
            simulation_id = cursor.lastrowid
            
            # Insert round-by-round outputs
            round_data = [(simulation_id, round_num + 1, output) 
                         for round_num, output in enumerate(result['round_outputs'])]
            cursor.executemany(
                'INSERT INTO round_outputs (simulation_id, round_num, output) VALUES (?, ?, ?)',
                round_data
            )
            
            # Commit every 100 simulations to avoid massive transactions
            if i % 100 == 0:
                conn.commit()
        
        # Complete the progress line
        print(f"\rProgress: 100% | Complete: {time.time() - start_time:.1f}s | Simulations: {num_simulations}/{num_simulations}")
        
        # Ensure all simulations are committed for this strategy
        conn.commit()
    
    conn.close()
    
    print(f"\nSimulations completed. Results stored in {db_path}")
    return db_path

def analyze_results(db_path='simulation_results.db'):
    """Analyze the simulation results and generate visualizations"""
    print("\nAnalyzing simulation results...")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    
    # Load the simulation results into a pandas DataFrame
    df = pd.read_sql_query("SELECT * FROM simulations", conn)
    
    # Try to import matplotlib for visualizations
    try:
        import matplotlib.pyplot as plt
        matplotlib_available = True
    except ImportError:
        print("Note: matplotlib not installed. Skipping visualizations.")
        matplotlib_available = False
    
    # Display basic statistics
    print("\nSummary Statistics:")
    for strategy in ['original', 'A', 'B', 'C']:
        strategy_df = df[df['strategy'] == strategy]
        print(f"\nStrategy {strategy}:")
        print(f"  Total Output:      Mean = {strategy_df['total_output'].mean():.2f}, SD = {strategy_df['total_output'].std():.2f}")
        print(f"  End WIP:           Mean = {strategy_df['end_wip'].mean():.2f}, SD = {strategy_df['end_wip'].std():.2f}")
        print(f"  Avg Cycle Time:    Mean = {strategy_df['avg_cycle_time'].mean():.2f}, SD = {strategy_df['avg_cycle_time'].std():.2f}")
    
    # Calculate confidence intervals
    confidence_level = 0.95
    z_score = 1.96  # For 95% confidence interval
    
    print("\nConfidence Intervals (95%):")
    for strategy in ['original', 'A', 'B', 'C']:
        strategy_df = df[df['strategy'] == strategy]
        n = len(strategy_df)
        
        # Total Output
        mean_output = strategy_df['total_output'].mean()
        std_output = strategy_df['total_output'].std()
        margin_output = z_score * (std_output / np.sqrt(n))
        
        # End WIP
        mean_wip = strategy_df['end_wip'].mean()
        std_wip = strategy_df['end_wip'].std()
        margin_wip = z_score * (std_wip / np.sqrt(n))
        
        # Average Cycle Time
        mean_cycle = strategy_df['avg_cycle_time'].mean()
        std_cycle = strategy_df['avg_cycle_time'].std()
        margin_cycle = z_score * (std_cycle / np.sqrt(n))
        
        print(f"\nStrategy {strategy}:")
        print(f"  Total Output:      {mean_output:.2f} ± {margin_output:.2f}")
        print(f"  End WIP:           {mean_wip:.2f} ± {margin_wip:.2f}")
        print(f"  Avg Cycle Time:    {mean_cycle:.2f} ± {margin_cycle:.2f}")
    
    # Set up a directory for visualizations
    viz_dir = 'simulation_visualizations'
    os.makedirs(viz_dir, exist_ok=True)
    
    # Generate visualizations if matplotlib is available
    if matplotlib_available:
        print("\nGenerating visualizations...")
        
        # Generate histograms for each metric
        metrics = {
            'total_output': 'Total Output',
            'end_wip': 'End WIP',
            'avg_cycle_time': 'Average Cycle Time'
        }
        
        for column, title in metrics.items():
            plt.figure(figsize=(12, 8))
            for strategy in ['original', 'A', 'B', 'C']:
                strategy_df = df[df['strategy'] == strategy]
                plt.hist(
                    strategy_df[column], 
                    alpha=0.5, 
                    bins=30,
                    label=f"Strategy {strategy}"
                )
            
            plt.title(f"Distribution of {title} Across {len(df) // 4} Simulations Per Strategy")
            plt.xlabel(title)
            plt.ylabel('Frequency')
            plt.legend()
            plt.tight_layout()
            
            # Save the figure
            plt.savefig(os.path.join(viz_dir, f"{column}_histogram.png"))
            plt.close()
        
        # Generate box plots for each metric
        for column, title in metrics.items():
            plt.figure(figsize=(10, 6))
            
            # Prepare data for box plot
            data = [df[df['strategy'] == s][column] for s in ['original', 'A', 'B', 'C']]
            
            # Create the box plot
            plt.boxplot(
                data,
                labels=['Original', 'A: Peak Capacity', 'B: Reduced Variability', 'C: Increased WIP'],
                showmeans=True
            )
            
            plt.title(f"Box Plot of {title} by Strategy")
            plt.ylabel(title)
            plt.tight_layout()
            
            # Save the figure
            plt.savefig(os.path.join(viz_dir, f"{column}_boxplot.png"))
            plt.close()
    else:
        print("\nSkipping visualizations (matplotlib not available)")
        print("To generate visualizations, install matplotlib: pip install matplotlib")
    
    # Generate a summary CSV file
    summary_df = df.groupby('strategy').agg({
        'total_output': ['mean', 'std', 'min', 'max'],
        'end_wip': ['mean', 'std', 'min', 'max'],
        'avg_cycle_time': ['mean', 'std', 'min', 'max']
    }).reset_index()
    
    summary_path = os.path.join(viz_dir, 'simulation_summary.csv')
    summary_df.to_csv(summary_path)
    
    print(f"\nVisualizations saved to {viz_dir}/")
    print(f"Summary statistics saved to {summary_path}")
    conn.close()

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Run mass simulations of the Fab Flow game.')
    parser.add_argument('--simulations', type=int, default=3000,
                        help='Number of simulations to run per strategy (default: 3000)')
    parser.add_argument('--output', type=str, default='simulation_results.db',
                        help='Output database file (default: simulation_results.db)')
    parser.add_argument('--analyze-only', action='store_true',
                        help='Only analyze existing results without running new simulations')
    
    args = parser.parse_args()
    
    if not args.analyze_only:
        start_time = time.time()
        db_path = run_mass_simulations(args.simulations, args.output)
        end_time = time.time()
        print(f"\nTotal simulation time: {(end_time - start_time) / 60:.2f} minutes")
    else:
        db_path = args.output
        if not os.path.exists(db_path):
            print(f"Error: Database '{db_path}' not found. Run simulations first.")
            return 1
    
    # Analyze the results
    analyze_results(db_path)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
