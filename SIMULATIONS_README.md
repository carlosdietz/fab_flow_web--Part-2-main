# Fab Flow Game Simulation Analysis Tools

This folder contains tools for running mass simulations of the Fab Flow game to generate statistically significant data about the different strategies.

## Files

- `run_simulations.py` - Advanced simulation tool with database storage and detailed analysis
- `simple_simulations.py` - Simplified version that outputs directly to CSV
- `simulation_requirements.txt` - Required Python packages

## Setup

1. Install the required dependencies:

```
pip install -r simulation_requirements.txt
```

## Running Mass Simulations

### Basic Usage (Simple CSV Output)

To run 3,000 simulations of each strategy and output to CSV:

```
python simple_simulations.py
```

This will create a file called `simulation_results.csv` with all the data.

### Advanced Usage (Database + Analysis)

To run the advanced simulation tool:

```
python run_simulations.py
```

Options:
- `--simulations 5000` - Change the number of simulations (default: 3000 per strategy)
- `--output custom_name.db` - Change the output database file name
- `--analyze-only` - Only analyze existing results without running new simulations

The advanced tool will:
1. Store all simulation results in an SQLite database
2. Generate statistical analysis including confidence intervals
3. Create visualizations in a folder called `simulation_visualizations/`
4. Output a summary CSV file with key statistics

## Understanding the Strategies

- **Original**: Base game with dice range 1-6 and start WIP of 4
- **Strategy A**: Increased capacity with dice range 1-7 and start WIP of 4
- **Strategy B**: Reduced variability with dice range 2-5 and start WIP of 4
- **Strategy C**: Increased WIP with dice range 1-6 and start WIP of 5

## Example Analysis

The tool will generate:
1. Histograms showing the distribution of Total Output, End WIP, and Average Cycle Time
2. Box plots comparing the four strategies
3. Statistical summaries with means, standard deviations, and 95% confidence intervals

This allows for a rigorous statistical comparison of which strategy performs best across thousands of simulations.
