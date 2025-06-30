#!/usr/bin/env python
"""
Simple Fab Flow Game Mass Simulation Tool

This script runs thousands of simulations of the Fab Flow game to generate
statistically significant data for comparing different strategies.

Usage:
  python simple_simulations.py

Creates a CSV file with the results from 3,000 simulations of each strategy.
"""
import os
import random
import pandas as pd
import time
import sys
from datetime import datetime

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
        "Strategy": strategy,
        "Total Output": total_output, 
        "End WIP": total_end_wip,
        "Avg Cycle Time": tracked_avg_cycle_time
    }

def run_mass_simulations(num_simulations=3000, output_file='simulation_results.csv'):
    """Run a large number of simulations for each strategy and save to CSV"""
    print(f"Starting {num_simulations} simulations per strategy (total: {num_simulations * 4})...")
    
    strategies = ['original', 'A', 'B', 'C']
    all_results = []
    
    # Run simulations for each strategy
    for strategy in strategies:
        print(f"\nRunning {num_simulations} simulations for strategy '{strategy}'...")
        start_time = time.time()
        
        # Create a simple progress indicator
        for i in range(num_simulations):
            if i % 100 == 0:
                progress = i / num_simulations * 100
                elapsed = time.time() - start_time
                est_total = elapsed / (i + 1) * num_simulations
                remaining = est_total - elapsed
                sys.stdout.write(f"\rProgress: {progress:.1f}% | Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s | Simulations: {i}/{num_simulations}")
                sys.stdout.flush()
                
            # Run a single simulation
            result = simulate_game(strategy)
            all_results.append(result)
        
        # Complete the progress line
        print(f"\rProgress: 100% | Complete: {time.time() - start_time:.1f}s | Simulations: {num_simulations}/{num_simulations}")
    
    # Convert results to DataFrame and save to CSV
    results_df = pd.DataFrame(all_results)
    
    # Add strategy labels
    strategy_labels = {
        'original': 'Base Game',
        'A': 'Increased Capacity (1-7)',
        'B': 'Reduced Variability (2-5)', 
        'C': 'Increased WIP (5)'
    }
    
    results_df['Strategy Label'] = results_df['Strategy'].map(strategy_labels)
    
    # Save to CSV
    results_df.to_csv(output_file, index=False)
    
    print(f"\nSimulations completed. Results stored in {output_file}")
    
    # Print summary statistics
    print("\nSummary Statistics:")
    summary = results_df.groupby('Strategy').agg({
        'Total Output': ['mean', 'std', 'min', 'max'],
        'End WIP': ['mean', 'std', 'min', 'max'],
        'Avg Cycle Time': ['mean', 'std', 'min', 'max']
    })
    
    print(summary)
    
    return output_file

if __name__ == "__main__":
    run_mass_simulations()
