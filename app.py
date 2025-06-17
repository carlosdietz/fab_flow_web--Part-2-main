import streamlit as st
import random
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import os
import datetime
from io import BytesIO
from io import BytesIO

st.set_page_config(page_title="Dice Game - Semiconductor Manufacturing Chain", layout="wide")

# Admin sidebar for data export - only visible if 'admin' query parameter is present
if 'admin' in st.query_params:
    with st.sidebar:
        st.title("Admin Tools")
        st.markdown("### Export Data")
        if st.button("Export to Excel"):
            try:
                if os.path.exists('data/game_results.db'):
                    conn = sqlite3.connect('data/game_results.db')
                    results_df = pd.read_sql_query("SELECT * FROM user_results", conn)
                    conn.close()
                    
                    # Reorder columns for better readability (matches the requested order)
                    column_order = [
                        'username', 'timestamp',
                        'quiz1_answer1', 'quiz1_answer2', 'quiz1_answer3', 'quiz1_answer4',
                        'game1_cycle_time', 'game1_output', 'game1_wip',
                        'prioritization_A', 'prioritization_B', 'prioritization_C',
                        'game2_A_cycle_time', 'game2_A_output', 'game2_A_wip',
                        'game2_B_cycle_time', 'game2_B_output', 'game2_B_wip',
                        'game2_C_cycle_time', 'game2_C_output', 'game2_C_wip',
                        'final_prioritization_A', 'final_prioritization_B', 'final_prioritization_C'
                    ]
                    
                    # Make sure we only include columns that exist in the dataframe
                    valid_columns = [col for col in column_order if col in results_df.columns]
                    
                    # Add any columns that weren't in our list at the end
                    for col in results_df.columns:
                        if col not in valid_columns and col != 'id':
                            valid_columns.append(col)
                    
                    # Select just the columns we want in the right order
                    ordered_df = results_df[valid_columns]
                    
                    # Create an Excel file in memory
                    excel_file = BytesIO()
                    ordered_df.to_excel(excel_file, index=False, engine='openpyxl')
                    excel_file.seek(0)
                    
                    # Create a timestamp for the filename
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    excel_filename = f"fab_flow_results_{timestamp}.xlsx"
                    
                    st.success(f"Data exported as Excel file")
                    
                    # Show a preview of the data
                    st.write("### Data Preview")
                    st.dataframe(ordered_df.head())
                    
                    # Provide download button for the Excel file
                    st.download_button(
                        label="📥 Download Excel File",
                        data=excel_file,
                        file_name=excel_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No database file found. Run the game first to generate data.")
            except Exception as e:
                st.error(f"Error exporting data: {str(e)}")

# --- Backend logic ---
NUM_STEPS = 10
NUM_ROUNDS = 20
START_WIP = 4
RAW_MATERIAL = float('inf')
DICE_RANGE = (1, 6)
ICONS = {'wip': '🟦', 'output': '💎', 'clock': '⏰'}

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
        return sum(cycle_times) / len(cycle_times)
    return 0

def simulate_multiple_rounds(num_rounds):
    """
    Simulate multiple rounds at once while maintaining all game logic.
    Returns the new round number (capped at NUM_ROUNDS).
    """
    dice_range = st.session_state.dice_range_override if st.session_state.dice_range_override is not None else DICE_RANGE
    target_round = min(st.session_state.round_num + num_rounds, NUM_ROUNDS)
    
    # Process each round
    while st.session_state.round_num < target_round:
        # Process one round
        (
            st.session_state.prev_incoming,
            throughputs,
            dice,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units,
            start_wip_per_step
        ) = process_round(
            st.session_state.stations,
            st.session_state.prev_incoming,
            dice_range,
            st.session_state.round_num,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            st.session_state.tracked_units
        )
        
        # Update the station outputs
        for i, s in enumerate(st.session_state.stations):
            s.output = throughputs[i]
            
        # Record the round results
        round_output = len(round_finished_units)
        st.session_state.round_outputs.append(round_output)
        st.session_state.dice_history.append(dice)
        st.session_state.throughputs_history.append(throughputs)
        st.session_state.end_wip_history.append(end_wip_per_step)
        st.session_state.total_end_wip_history.append(total_end_wip)
        st.session_state.round_finished_units_history.append(round_finished_units)
        if 'start_wip_history' not in st.session_state:
            st.session_state.start_wip_history = []
        st.session_state.start_wip_history.append(start_wip_per_step)
        
        # Advance round counter
        st.session_state.round_num += 1
    
    return st.session_state.round_num

def save_data_to_database(username):
    """
    Saves all user data to SQLite database including quiz answers and game results
    """
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Connect to SQLite database
    conn = sqlite3.connect('data/game_results.db')
    c = conn.cursor()
    
    # Create table if it doesn't exist - with separate columns for each data point
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        timestamp TEXT,
        
        quiz1_answer1 TEXT,
        quiz1_answer2 TEXT,
        quiz1_answer3 TEXT,
        quiz1_answer4 TEXT,
        
        game1_cycle_time REAL,
        game1_output INTEGER,
        game1_wip INTEGER,
        
        prioritization_A TEXT,
        prioritization_B TEXT,
        prioritization_C TEXT,
        
        game2_A_cycle_time REAL,
        game2_A_output INTEGER,
        game2_A_wip INTEGER,
        
        game2_B_cycle_time REAL,
        game2_B_output INTEGER,
        game2_B_wip INTEGER,
        
        game2_C_cycle_time REAL,
        game2_C_output INTEGER,
        game2_C_wip INTEGER,
        
        final_prioritization_A TEXT,
        final_prioritization_B TEXT,
        final_prioritization_C TEXT
    )
    ''')
    
    # Extract data from session state
    quiz1_answers = st.session_state.get('quiz_answers', ['', '', '', ''])
    while len(quiz1_answers) < 4:
        quiz1_answers.append('')
    
    # Game 1 results - using defaults if not available
    original_game_results = st.session_state.get('original_game_results', {'Total Output': 0, 'End WIP': 0, 'Tracked AVG Cycle Time': 0})
    game1_cycle_time = original_game_results.get('Tracked AVG Cycle Time', 0)
    game1_output = original_game_results.get('Total Output', 0)
    game1_wip = original_game_results.get('End WIP', 0)
    
    # Second quiz prioritization
    second_quiz = st.session_state.get('second_quiz', ['', '', ''])
    while len(second_quiz) < 3:
        second_quiz.append('')
    
    # Game 2 results for all alternatives - using defaults if not available
    second_game_results = st.session_state.get('second_game_results', {
        'A': {'Total Output': 0, 'End WIP': 0, 'Tracked AVG Cycle Time': 0},
        'B': {'Total Output': 0, 'End WIP': 0, 'Tracked AVG Cycle Time': 0},
        'C': {'Total Output': 0, 'End WIP': 0, 'Tracked AVG Cycle Time': 0}
    })
    
    # Extract each value individually to ensure proper data types
    game2_A_cycle_time = second_game_results.get('A', {}).get('Tracked AVG Cycle Time', 0)
    game2_A_output = second_game_results.get('A', {}).get('Total Output', 0)
    game2_A_wip = second_game_results.get('A', {}).get('End WIP', 0)
    
    game2_B_cycle_time = second_game_results.get('B', {}).get('Tracked AVG Cycle Time', 0)
    game2_B_output = second_game_results.get('B', {}).get('Total Output', 0)
    game2_B_wip = second_game_results.get('B', {}).get('End WIP', 0)
    
    game2_C_cycle_time = second_game_results.get('C', {}).get('Tracked AVG Cycle Time', 0)
    game2_C_output = second_game_results.get('C', {}).get('Total Output', 0)
    game2_C_wip = second_game_results.get('C', {}).get('End WIP', 0)
    
    # Final quiz prioritization
    third_quiz = st.session_state.get('third_quiz', ['', '', ''])
    while len(third_quiz) < 3:
        third_quiz.append('')
    
    # Current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert data into database - explicitly passing each value
    c.execute('''
    INSERT INTO user_results (
        username, timestamp,
        quiz1_answer1, quiz1_answer2, quiz1_answer3, quiz1_answer4,
        game1_cycle_time, game1_output, game1_wip,
        prioritization_A, prioritization_B, prioritization_C,
        game2_A_cycle_time, game2_A_output, game2_A_wip,
        game2_B_cycle_time, game2_B_output, game2_B_wip,
        game2_C_cycle_time, game2_C_output, game2_C_wip,
        final_prioritization_A, final_prioritization_B, final_prioritization_C
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        username, timestamp,
        quiz1_answers[0], quiz1_answers[1], quiz1_answers[2], quiz1_answers[3],
        game1_cycle_time, game1_output, game1_wip,
        second_quiz[0], second_quiz[1], second_quiz[2],
        game2_A_cycle_time, game2_A_output, game2_A_wip,
        game2_B_cycle_time, game2_B_output, game2_B_wip,
        game2_C_cycle_time, game2_C_output, game2_C_wip,
        third_quiz[0], third_quiz[1], third_quiz[2]
    ))
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    return True

# --- Streamlit UI ---

# Initialize session state variables
if "show_round_0" not in st.session_state:
    st.session_state.show_round_0 = False

if 'page' not in st.session_state:
    st.session_state.page = 'username_entry'
    st.session_state.quiz_answers = [""]*4
    st.session_state.quiz_submitted = False
    st.session_state.stations = None
    st.session_state.prev_incoming = [[] for _ in range(NUM_STEPS)]
    st.session_state.finished_units = []
    st.session_state.finished_cycles = []
    st.session_state.round_outputs = []
    st.session_state.dice_history = []
    st.session_state.throughputs_history = []
    st.session_state.end_wip_history = []
    st.session_state.total_end_wip_history = []
    st.session_state.round_finished_units_history = []
    st.session_state.round_num = 0
    st.session_state.tracked_units = {}
    st.session_state.second_quiz = ["", "", ""]
    st.session_state.second_quiz_submitted = False
    st.session_state.second_game_results = {}
    st.session_state.second_game_user_choice = None
    st.session_state.third_quiz = ["", "", ""]
    st.session_state.third_quiz_submitted = False
    st.session_state.dice_range_override = None
    st.session_state.username = ""
    # Initialize results storage
    st.session_state.original_game_results = {
        "Total Output": 0,
        "End WIP": 0,
        "Tracked AVG Cycle Time": 0
    }

if 'start_wip_history' not in st.session_state:
    st.session_state.start_wip_history = []

def reset_game_state():
    st.session_state.stations = initialize_stations(START_WIP)
    st.session_state.prev_incoming = [[] for _ in range(NUM_STEPS)]
    st.session_state.finished_units = []
    st.session_state.finished_cycles = []
    st.session_state.round_outputs = []
    st.session_state.dice_history = []
    st.session_state.throughputs_history = []
    st.session_state.end_wip_history = []
    st.session_state.total_end_wip_history = []
    st.session_state.round_finished_units_history = []
    st.session_state.round_num = 0
    st.session_state.tracked_units = {}
    st.session_state.dice_range_override = None

# --- Username Entry Page ---
if st.session_state.page == 'username_entry':
    st.title("Semiconductor Manufacturing Chain Simulation")
    st.markdown("### Welcome! Please enter your username to begin")
    
    username = st.text_input("Enter your username:", value=st.session_state.username)
    
    if st.button("Start"):
        if username.strip():
            st.session_state.username = username.strip()
            st.session_state.page = 'welcome'
            st.rerun()
        else:
            st.error("Please enter a username to continue.")
    st.stop()

# --- Welcome Page ---
elif st.session_state.page == 'welcome':
    try:
        st.image("images/factory_bg.jpg", width=900)
    except Exception:
        st.warning("Background image not found.")
    st.markdown("<h1 style='color:#1a237e;'>Welcome to the Dice Game!</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:18px;'>
    <ul>
      <li>You control a <b>10-Step Manufacturing Chain</b> (From raw materials to finished goods)</li>
      <li>In each round, a <b>random value from 1 to 6</b> represents process capacity for each station</li>
      <li>All process steps begin with <b>4 WIP</b>, except step 1 which has unlimited raw material</li>
      <li><b>Throughput = minimum(current WIP, rolled number)</b></li>
      <li>No skipping or parallel processing</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h2 style='color:#388e3c;'>Goal of the Game: Maximize finished goods output & minimize WIP and Cycle Time!</h2>", unsafe_allow_html=True)
    if st.button("Next"):
        st.session_state.page = 'quiz'
        st.rerun()

# --- Quiz Page ---
elif st.session_state.page == 'quiz':
    st.markdown("### Quiz: Please answer the following questions before starting the game.")
    quiz_questions = [
        "What is the average of the capacity per round and station?",
        "What do you estimate the output will be after 20 rounds?",
        "What is the raw process time?",
        "What could the average cycle time be?"
    ]
    correct_answers = [
        "Expected Value of a Die Roll = (1+2+3+4+5+6)/6 = 3.5",
        "Estimates e.g. 70 finished Units after 20 rounds (20 * 3.5 = 70)",
        "A unit can pass through max. one station per round, so RPT is 10 with 10 stations.",
        "Estimates, but higher than 10, because of Waiting Times in Production Stations!"
    ]
    
    quiz_answers = st.session_state.quiz_answers
    for i, q in enumerate(quiz_questions):
        quiz_answers[i] = st.text_input(f"{i+1}. {q}", value=quiz_answers[i], key=f"quiz_{i}")
        # Show the correct answer if quiz is submitted
        if st.session_state.quiz_submitted:
            st.success(f"**Correct Answer:** {correct_answers[i]}")
            
    # Show either submit or start game button based on quiz_submitted state
    if not st.session_state.quiz_submitted:
        if st.button("Submit Quiz"):
            if all(a.strip() for a in quiz_answers):
                st.session_state.quiz_submitted = True
                st.session_state.quiz_answers = quiz_answers
                st.rerun()  # Rerun to update the page with correct answers
            else:
                st.warning("Please answer all questions!")
    else:
        if st.button("Start Game"):
            st.session_state.stations = initialize_stations(START_WIP)
            st.session_state.round_num = 0
            st.session_state.show_round_0 = True
            st.session_state.page = 'initial'
            st.rerun()

# --- Game Board Page ---
elif st.session_state.page in ['initial', 'round']:
    if st.session_state.show_round_0:
        st.markdown("## Round 0")
        st.markdown("### Manufacturing Chain")
        round0_wip = [999] + [4]*(NUM_STEPS-1)
        floor_cols = st.columns(NUM_STEPS)
        for i in range(NUM_STEPS):
            with floor_cols[i]:
                try:
                    st.image("images/machine.png", width=100)
                except Exception:
                    st.warning("Missing image: images/machine.png")
                st.markdown(f"**Step {i+1}**")
                
                # Initial WIP with small images
                if round0_wip[i] == 999:
                    st.markdown("Initial WIP:")
                    try:
                        st.image("infinity.png", width=30)
                    except Exception:
                        st.markdown("∞")
                else:
                    st.markdown(f"Initial WIP: {round0_wip[i]}")
                if i != 0 and round0_wip[i] != 999:
                    if round0_wip[i] > 17:
                        wafer_imgs = ["images/wafer_available.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_imgs = ["images/wafer_available.png"] * round0_wip[i]
                    st.image(wafer_imgs, width=18)
        
        st.markdown("---")
        st.markdown("### KPI Panel")
        # Create a horizontal layout for KPI metrics and buttons
        kpi_col, buttons_col = st.columns([3, 1])
        
        with kpi_col:
            # Create a light gray box for KPI metrics with more padding
            total_wip = sum(round0_wip[1:])
            
            # Create HTML content for the metrics inside the gray box
            html_content = f"""
            <div style="background-color:#f0f2f5; padding:25px; border-radius:8px; margin-bottom:15px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Round Output:</p>
                        <p style='font-size:24px; font-weight:bold;'>0</p>
                    </div>
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total Output:</p>
                        <p style='font-size:24px; font-weight:bold;'>0</p>
                    </div>
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total WIP:</p>
                        <p style='font-size:24px; font-weight:bold;'>{total_wip}</p>
                    </div>
                </div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)
        
        # Next round button in the right column
        with buttons_col:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            if st.button("Next Round", key="next_round0_btn", use_container_width=True):
                st.session_state.show_round_0 = False
                st.session_state.round_num = 1
                st.session_state.page = 'round'
                st.rerun()
        st.stop()
        
    if st.session_state.page == 'initial':
        reset_game_state()
        st.session_state.round_num = 1

    st.markdown(f"## Round {st.session_state.round_num}")

    # Only process round if not already processed for this round
    # --- FIX: Always use dice_range fallback logic ---
    dice_range = st.session_state.dice_range_override if st.session_state.dice_range_override is not None else DICE_RANGE
    if len(st.session_state.dice_history) < st.session_state.round_num:
        (
            st.session_state.prev_incoming,
            throughputs,
            dice,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units,
            start_wip_per_step
        ) = process_round(
            st.session_state.stations,
            st.session_state.prev_incoming,
            dice_range,
            st.session_state.round_num,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            st.session_state.tracked_units
        )
        # After process_round, set output for each station
        for i, s in enumerate(st.session_state.stations):
            s.output = throughputs[i]
        round_output = len(round_finished_units)
        st.session_state.round_outputs.append(round_output)
        st.session_state.dice_history.append(dice)
        st.session_state.throughputs_history.append(throughputs)
        st.session_state.end_wip_history.append(end_wip_per_step)
        st.session_state.total_end_wip_history.append(total_end_wip)
        st.session_state.round_finished_units_history.append(round_finished_units)
        if 'start_wip_history' not in st.session_state:
            st.session_state.start_wip_history = []
        st.session_state.start_wip_history.append(start_wip_per_step)
    else:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]
        if 'start_wip_history' in st.session_state and len(st.session_state.start_wip_history) >= st.session_state.round_num:
            start_wip_per_step = st.session_state.start_wip_history[st.session_state.round_num-1]
        else:
            start_wip_per_step = [4]*NUM_STEPS

    # Always define dice, throughputs, end_wip_per_step, total_end_wip, start_wip_per_step for the UI below
    if len(st.session_state.dice_history) >= st.session_state.round_num:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]
        if len(st.session_state.start_wip_history) >= st.session_state.round_num:
            start_wip_per_step = st.session_state.start_wip_history[st.session_state.round_num-1]
        else:            start_wip_per_step = [4]*NUM_STEPS
    
    # Show stations as machines with wafers
    st.markdown("### Manufacturing Chain")
    floor_cols = st.columns(NUM_STEPS)
    for i, s in enumerate(st.session_state.stations):
        with floor_cols[i]:
            try:
                st.image("images/machine.png", width=100)
            except Exception:
                st.warning("Missing image: images/machine.png")
            st.markdown(f"**Step {i+1}**")
            
            # Start with Start WIP (first value)
            if i == 0:
                st.markdown(f"**Start WIP:**")
                try:
                    st.image("infinity.png", width=30)
                except Exception:
                    st.markdown("∞")
            else:
                available_wip = start_wip_per_step[i] if start_wip_per_step[i] != 999 else '∞'
                st.markdown(f"**Start WIP:** {available_wip if available_wip != 999 else '∞'}")
                if isinstance(available_wip, int) and available_wip > 0:
                    if available_wip > 17:
                        wafer_imgs = ["images/wafer_available.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_imgs = ["images/wafer_available.png"] * available_wip
                    st.image(wafer_imgs, width=18)
            
            # Show dice image (make it bigger)
            try:
                st.image(f"images/dice{dice[i]}.png", width=45)
            except Exception:
                st.warning(f"Missing image: images/dice{dice[i]}.png")
            
            # Add Throughput value
            st.markdown(f"**Throughput:** {throughputs[i]}")
            
            # End WIP after throughput
            if i != 0:
                end_wip_val = s.wip if s.wip != RAW_MATERIAL else 999
                st.markdown(f"**End WIP:** {end_wip_val if end_wip_val != 999 else '∞'}")
                if isinstance(end_wip_val, int) and end_wip_val > 0:
                    if end_wip_val > 17:
                        wafer_arrived_imgs = ["images/wafer_arrived.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_arrived_imgs = ["images/wafer_arrived.png"] * end_wip_val
                    st.image(wafer_arrived_imgs, width=18)
    
    st.markdown("---")
    st.markdown("### KPI Panel")
    
    # Create a horizontal layout for KPI metrics and buttons
    kpi_col, buttons_col = st.columns([3, 1])
    
    with kpi_col:
        # Create a light gray box for KPI metrics with more padding
        total_output = sum(st.session_state.round_outputs)
        round_output = st.session_state.round_outputs[-1]
        total_wip = sum(e for e in end_wip_per_step[1:10] if isinstance(e, int))
        
        # Create HTML content for the metrics inside the gray box
        html_content = f"""
        <div style="background-color:#f0f2f5; padding:25px; border-radius:8px; margin-bottom:15px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Round Output:</p>
                    <p style='font-size:24px; font-weight:bold;'>{round_output}</p>
                </div>
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total Output:</p>
                    <p style='font-size:24px; font-weight:bold;'>{total_output}</p>
                </div>
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total WIP:</p>
                    <p style='font-size:24px; font-weight:bold;'>{total_wip}</p>
                </div>
            </div>
        </div>
        """
        st.markdown(html_content, unsafe_allow_html=True)
    
    # Next round or end buttons in the right column
    with buttons_col:
        if st.session_state.round_num < NUM_ROUNDS:
            # Make buttons larger with custom styling
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            if st.button("Next Round", use_container_width=True):
                st.session_state.round_num += 1
                st.session_state.page = 'round'  # <-- Changed to 'round' for main game
                st.rerun()
            
            rounds_to_skip = min(5, NUM_ROUNDS - st.session_state.round_num)
            if rounds_to_skip > 0:
                if st.button(f"Skip {rounds_to_skip} Rounds", use_container_width=True):
                    # Simulate multiple rounds using our helper function
                    simulate_multiple_rounds(rounds_to_skip)
                    st.session_state.page = 'round'  # <-- Changed to 'round' for main game
                    st.rerun()
        else:
            if st.button("Show End Results", use_container_width=True):  # <-- Changed text
                st.session_state.page = 'end'  # <-- Changed to 'end' for main game
                st.rerun()

# --- End Results Page ---
elif st.session_state.page == 'end':
    total_output = sum(st.session_state.round_outputs)
    total_end_wip = st.session_state.total_end_wip_history[-1] if st.session_state.total_end_wip_history else 0
    tracked_avg_cycle_time = get_tracked_avg_cycle_time(st.session_state.tracked_units)
    
    # Store original game results for later comparison
    st.session_state.original_game_results = {
        "Total Output": total_output,
        "End WIP": total_end_wip,
        "Tracked AVG Cycle Time": tracked_avg_cycle_time
    }
    
    st.markdown("## GAME END")
    st.success(f"Total Output: {total_output} {ICONS['output']}")
    st.info(f"Tracked AVG CYCLE TIME: {tracked_avg_cycle_time:.2f} {ICONS['clock']}")
    st.warning(f"TOTAL WIP: {total_end_wip} {ICONS['wip']}")
    
    # Always show the Next (Second Quiz) button at the end of the first game
    if st.button("Next (Second Quiz)"):
        st.session_state.page = 'second_quiz'
        st.rerun()

# --- Second Quiz Page ---
elif st.session_state.page == 'second_quiz':
    st.markdown("### Second Quiz: Prioritize the following options (1 = highest priority, 3 = lowest):")
    options = [
        "A) Increase peak Machine Capacity to random (1,2,3,4,5,6,7)",
        "B) Reduce Variability of the Capacity to random (2,3,4,5)",
        "C) Increase Start WIP at each step to 5"
    ]
    second_quiz = st.session_state.second_quiz
    for i, opt in enumerate(options):
        second_quiz[i] = st.selectbox(f"{opt}", ["", "1", "2", "3"], index=["", "1", "2", "3"].index(second_quiz[i]), key=f"second_quiz_{i}")
    if st.button("Submit Priorities"):
        if all(v in {"1", "2", "3"} for v in second_quiz) and len(set(second_quiz)) == 3:
            st.session_state.second_quiz_submitted = True
        else:
            st.warning("Please assign unique priorities 1, 2, and 3!")
    if st.session_state.second_quiz_submitted:
        st.success("Priorities submitted!")
        if st.button("Start Second Game"):
            st.session_state.page = 'second_game'
            st.rerun()

# --- Second Game and Simulations ---
elif st.session_state.page == 'second_game':
    # Simulate all alternatives
    priorities = st.session_state.second_quiz
    options = ["A", "B", "C"]
    top_choice = options[priorities.index("1")]
    st.session_state.second_game_user_choice = top_choice
    settings = {
        "A": {"dice_range": (1, 7), "start_wip": 4},
        "B": {"dice_range": (2, 5), "start_wip": 4},
        "C": {"dice_range": (1, 6), "start_wip": 5},
    }
    results = {}
    for opt in options:
        stations = initialize_stations(settings[opt]["start_wip"])
        prev_incoming = [[] for _ in range(NUM_STEPS)]
        finished_units = []
        finished_cycles = []
        tracked_units = {}
        round_outputs = []
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
                _  # start_wip_per_step (unused in simulation)
            ) = process_round(
                stations,
                prev_incoming,
                settings[opt]["dice_range"],
                round_num,
                finished_units,
                finished_cycles,
                tracked_units
            )
            round_outputs.append(len(round_finished_units))
        total_output = sum(round_outputs)
        tracked_avg_cycle_time = get_tracked_avg_cycle_time(tracked_units)
        results[opt] = {
            "Total Output": total_output,
            "End WIP": total_end_wip,
            "Tracked AVG Cycle Time": tracked_avg_cycle_time
        }
    st.session_state.second_game_results = results
    # Now play the actual game for the user's top choice
    reset_game_state()
    st.session_state.stations = initialize_stations(settings[top_choice]["start_wip"])
    st.session_state.dice_range_override = settings[top_choice]["dice_range"]
    st.session_state.round_num = 1
    st.session_state.page = 'second_game_round'
    st.rerun()

elif st.session_state.page == 'second_game_round':
    # Show Round 0 for second game
    if st.session_state.round_num == 1 and not getattr(st.session_state, "second_game_round0_done", False):
        st.markdown("## Round 0")
        st.markdown("### Manufacturing Chain")
        
        # Use the correct start_wip for the selected option
        top_choice = st.session_state.second_game_user_choice
        settings = {
            "A": {"dice_range": (1, 7), "start_wip": 4},
            "B": {"dice_range": (2, 5), "start_wip": 4},
            "C": {"dice_range": (1, 6), "start_wip": 5},        }
        
        round0_wip = [999] + [settings[top_choice]["start_wip"]]*(NUM_STEPS-1)
        floor_cols = st.columns(NUM_STEPS)
        for i in range(NUM_STEPS):
            with floor_cols[i]:
                try:
                    st.image("images/machine.png", width=100)
                except Exception:
                    st.warning("Missing image: images/machine.png")
                
                st.markdown(f"**Step {i+1}**")
                
                # Initial WIP with small images
                if round0_wip[i] == 999:
                    st.markdown("Initial WIP:")
                    try:
                        st.image("infinity.png", width=30)
                    except Exception:
                        st.markdown("∞")
                else:
                    st.markdown(f"Initial WIP: {round0_wip[i]}")
                if i != 0 and round0_wip[i] != 999:
                    if round0_wip[i] > 17:
                        wafer_imgs = ["images/wafer_available.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_imgs = ["images/wafer_available.png"] * round0_wip[i]
                    st.image(wafer_imgs, width=18)
        
        st.markdown("---")
        st.markdown("### KPI Panel")
        
        # Create a horizontal layout for KPI metrics and buttons
        kpi_col, buttons_col = st.columns([3, 1])
        
        with kpi_col:
            # Create a light gray box for KPI metrics with more padding
            total_wip = sum(round0_wip[1:])
            
            # Create HTML content for the metrics inside the gray box
            html_content = f"""
            <div style="background-color:#f0f2f5; padding:25px; border-radius:8px; margin-bottom:15px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Round Output:</p>
                        <p style='font-size:24px; font-weight:bold;'>0</p>
                    </div>
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total Output:</p>
                        <p style='font-size:24px; font-weight:bold;'>0</p>
                    </div>
                    <div style="flex: 1; text-align:center;">
                        <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total WIP:</p>
                        <p style='font-size:24px; font-weight:bold;'>{total_wip}</p>
                    </div>
                </div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)
          
        # Next round button in the right column
        with buttons_col:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            if st.button("Next Round", key="second_game_next_round0_btn", use_container_width=True):
                # Important: When going from Round 0 to Round 1 in second game
                # 1. Set round_num to 1
                # 2. Do NOT reset histories
                # 3. Create a special flag to indicate we're done with Round 0
                st.session_state.round_num = 1
                st.session_state.second_game_round0_done = True
                st.rerun()
        st.stop()    # Regular rounds (1-20) display for second game
    # Show the current round number
    st.markdown(f"## Round {st.session_state.round_num}")
    st.markdown("### Manufacturing Chain")

    # Process round logic - similar to main game but with user's chosen dice_range
    dice_range = st.session_state.dice_range_override if st.session_state.dice_range_override is not None else DICE_RANGE
    if len(st.session_state.dice_history) < st.session_state.round_num:
        (
            st.session_state.prev_incoming,
            throughputs,
            dice,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units,
            start_wip_per_step
        ) = process_round(
            st.session_state.stations,
            st.session_state.prev_incoming,
            dice_range,
            st.session_state.round_num,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            st.session_state.tracked_units
        )
        # After process_round, set output for each station
        for i, s in enumerate(st.session_state.stations):
            s.output = throughputs[i]
        round_output = len(round_finished_units)
        st.session_state.round_outputs.append(round_output)
        st.session_state.dice_history.append(dice)
        st.session_state.throughputs_history.append(throughputs)
        st.session_state.end_wip_history.append(end_wip_per_step)
        st.session_state.total_end_wip_history.append(total_end_wip)
        st.session_state.round_finished_units_history.append(round_finished_units)
        if 'start_wip_history' not in st.session_state:
            st.session_state.start_wip_history = []
        st.session_state.start_wip_history.append(start_wip_per_step)
    else:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]
        if 'start_wip_history' in st.session_state and len(st.session_state.start_wip_history) >= st.session_state.round_num:
            start_wip_per_step = st.session_state.start_wip_history[st.session_state.round_num-1]
        else:
            start_wip_per_step = [4]*NUM_STEPS
              # Removed duplicate round number and title
    floor_cols = st.columns(NUM_STEPS)
    for i, s in enumerate(st.session_state.stations):
        with floor_cols[i]:
            try:
                st.image("images/machine.png", width=100)
            except Exception:
                st.warning("Missing image: images/machine.png")
            st.markdown(f"**Step {i+1}**")
            
            # Start with Start WIP (first value)
            if i == 0:
                st.markdown(f"**Start WIP:**")
                try:
                    st.image("infinity.png", width=30)
                except Exception:
                    st.markdown("∞")
            else:
                available_wip = start_wip_per_step[i] if start_wip_per_step[i] != 999 else '∞'
                st.markdown(f"**Start WIP:** {available_wip if available_wip != 999 else '∞'}")
                if isinstance(available_wip, int) and available_wip > 0:
                    if available_wip > 17:
                        wafer_imgs = ["images/wafer_available.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_imgs = ["images/wafer_available.png"] * available_wip
                    st.image(wafer_imgs, width=18)
            
            # Show dice image (make it bigger)
            try:
                st.image(f"images/dice{dice[i]}.png", width=45)
            except Exception:
                st.warning(f"Missing image: images/dice{dice[i]}.png")
            
            # Add Throughput value
            st.markdown(f"**Throughput:** {throughputs[i]}")
            
            # End WIP after throughput
            if i != 0:
                end_wip_val = s.wip if s.wip != RAW_MATERIAL else 999
                st.markdown(f"**End WIP:** {end_wip_val if end_wip_val != 999 else '∞'}")
                if isinstance(end_wip_val, int) and end_wip_val > 0:
                    if end_wip_val > 17:
                        wafer_arrived_imgs = ["images/wafer_arrived.png"] * 17 + ["images/threeDots.png"]
                    else:
                        wafer_arrived_imgs = ["images/wafer_arrived.png"] * end_wip_val
                    st.image(wafer_arrived_imgs, width=18)
    
    st.markdown("---")
    st.markdown("### KPI Panel")
    
    # Create a horizontal layout for KPI metrics and buttons
    kpi_col, buttons_col = st.columns([3, 1])
    
    with kpi_col:
        # Create a light gray box for KPI metrics with more padding
        total_output = sum(st.session_state.round_outputs)
        round_output = st.session_state.round_outputs[-1]
        total_wip = sum(e for e in end_wip_per_step[1:10] if isinstance(e, int))
        
        # Create HTML content for the metrics inside the gray box
        html_content = f"""
        <div style="background-color:#f0f2f5; padding:25px; border-radius:8px; margin-bottom:15px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Round Output:</p>
                    <p style='font-size:24px; font-weight:bold;'>{round_output}</p>
                </div>
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total Output:</p>
                    <p style='font-size:24px; font-weight:bold;'>{total_output}</p>
                </div>
                <div style="flex: 1; text-align:center;">
                    <p style='font-weight:bold; margin-bottom:8px; font-size:20px;'>Total WIP:</p>
                    <p style='font-size:24px; font-weight:bold;'>{total_wip}</p>
                </div>
            </div>
        </div>
        """
        st.markdown(html_content, unsafe_allow_html=True)
    
    # Next round or end buttons in the right column
    with buttons_col:
        if st.session_state.round_num < NUM_ROUNDS:
            # Make buttons larger with custom styling
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            if st.button("Next Round", use_container_width=True):
                st.session_state.round_num += 1
                st.session_state.page = 'second_game_round'
                st.rerun()
            
            rounds_to_skip = min(5, NUM_ROUNDS - st.session_state.round_num)
            if rounds_to_skip > 0:
                if st.button(f"Skip {rounds_to_skip} Rounds", use_container_width=True):
                    # Simulate multiple rounds using our helper function
                    simulate_multiple_rounds(rounds_to_skip)
                    st.session_state.page = 'second_game_round'
                    st.rerun()
        else:
            # Position the Show Comparison button in the same place as Next Round
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            if st.button("Show Comparison", use_container_width=True):
                st.session_state.page = 'comparison'
                st.rerun()

# --- Comparison Page ---
elif st.session_state.page == 'comparison':
    st.markdown("## Comparison of Alternatives")
    
    # Add safety check to prevent attribute errors
    if not hasattr(st.session_state, 'second_game_results') or not st.session_state.second_game_results:
        st.error("Missing game results data. Please restart the game.")
        if st.button("Return to Welcome Page"):
            st.session_state.page = 'welcome'
            st.rerun()
        st.stop()
        
    if not hasattr(st.session_state, 'original_game_results') or not st.session_state.original_game_results:
        st.session_state.original_game_results = {
            "Total Output": 0,
            "End WIP": 0,
            "Tracked AVG Cycle Time": 0
        }
        st.warning("Original game results were missing. Using default values.")
    
    results = st.session_state.second_game_results
    original = st.session_state.original_game_results

    # Prepare data for diagrams and tables (add "Original" as the first row)
    df = pd.DataFrame({
        "Alternative": ["Original", "A", "B", "C"],
        "Total Output": [
            original["Total Output"],
            results["A"]["Total Output"],
            results["B"]["Total Output"],
            results["C"]["Total Output"]
        ],
        "End WIP": [
            original["End WIP"],
            results["A"]["End WIP"],
            results["B"]["End WIP"],
            results["C"]["End WIP"]
        ],
        "Tracked AVG Cycle Time": [
            original["Tracked AVG Cycle Time"],
            results["A"]["Tracked AVG Cycle Time"],
            results["B"]["Tracked AVG Cycle Time"],
            results["C"]["Tracked AVG Cycle Time"]
        ],
    })

    kpi_cols = st.columns(3)
    # WIP
    with kpi_cols[0]:
        st.markdown("<h4 style='color:#1976d2;'>Total WIP</h4>", unsafe_allow_html=True)
        fig = go.Figure([go.Bar(
            x=df["Alternative"],
            y=df["End WIP"],
            marker_color=["#757575", "#1976d2", "#64b5f6", "#90caf9"]
        )])
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["Alternative", "End WIP"]].set_index("Alternative"), use_container_width=True)
    # Output
    with kpi_cols[1]:
        st.markdown("<h4 style='color:#388e3c;'>Total Output</h4>", unsafe_allow_html=True)
        fig = go.Figure([go.Bar(
            x=df["Alternative"],
            y=df["Total Output"],
            marker_color=["#757575", "#388e3c", "#81c784", "#c8e6c9"]
        )])
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["Alternative", "Total Output"]].set_index("Alternative"), use_container_width=True)
    # Cycle Time
    with kpi_cols[2]:
        st.markdown("<h4 style='color:#fbc02d;'>Tracked AVG Cycle Time</h4>", unsafe_allow_html=True)
        fig = go.Figure([go.Bar(
            x=df["Alternative"],
            y=df["Tracked AVG Cycle Time"],
            marker_color=["#757575", "#fbc02d", "#ffe082", "#fff9c4"]
        )])
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["Alternative", "Tracked AVG Cycle Time"]].set_index("Alternative"), use_container_width=True)

    st.markdown(f"You played: Option {st.session_state.second_game_user_choice}")
    if st.button("Next (Final Quiz)"):
        st.session_state.page = 'third_quiz'
        st.rerun()

# --- Third Quiz Page ---
elif st.session_state.page == 'third_quiz':
    st.markdown("### Final Quiz: Now that you have seen the results, please prioritize the following options again (1 = highest priority, 3 = lowest):")
    options = [
        "A) Increase peak Machine Capacity to random (1,2,3,4,5,6,7)",
        "B) Reduce Variability of the Capacity to random (2,3,4,5)",
        "C) Increase Start WIP at each step to 5"
    ]
    third_quiz = st.session_state.third_quiz
    for i, opt in enumerate(options):
        third_quiz[i] = st.selectbox(f"{opt}", ["", "1", "2", "3"], index=["", "1", "2", "3"].index(third_quiz[i]), key=f"third_quiz_{i}")
    if st.button("Submit Final Priorities"):
        if all(v in {"1", "2", "3"} for v in third_quiz) and len(set(third_quiz)) == 3:
            st.session_state.third_quiz_submitted = True
        else:
            st.warning("Please assign unique priorities 1, 2, and 3!")
    if st.session_state.third_quiz_submitted:
        st.success("Final priorities submitted!")
        if st.button("Finish"):
            st.session_state.page = 'thank_you'
            st.rerun()

# --- Thank You Page ---
elif st.session_state.page == 'thank_you':
    st.balloons()
    st.markdown("<h1 style='color:#388e3c;'>Thank you for playing the Dice Game!</h1>", unsafe_allow_html=True)
    st.markdown("We hope you enjoyed learning about semiconductor manufacturing flow and the impact of variability.")
    
    # Save all data to the database
    try:
        save_data_to_database(st.session_state.username)
        st.success(f"Your game data has been successfully saved with username: {st.session_state.username}")
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
    
    # Only show database viewing/export options for admin users
    if 'admin' in st.query_params:
        st.markdown("### Admin View: Database Contents")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("View Database Contents"):
                try:
                    conn = sqlite3.connect('data/game_results.db')
                    results_df = pd.read_sql_query("SELECT * FROM user_results", conn)
                    conn.close()
                    
                    # Reorder columns for better readability
                    column_order = [
                        'username', 'timestamp',
                        'quiz1_answer1', 'quiz1_answer2', 'quiz1_answer3', 'quiz1_answer4',
                        'game1_cycle_time', 'game1_output', 'game1_wip',
                        'prioritization_A', 'prioritization_B', 'prioritization_C',
                        'game2_A_cycle_time', 'game2_A_output', 'game2_A_wip',
                        'game2_B_cycle_time', 'game2_B_output', 'game2_B_wip',
                        'game2_C_cycle_time', 'game2_C_output', 'game2_C_wip',
                        'final_prioritization_A', 'final_prioritization_B', 'final_prioritization_C'
                    ]
                    
                    # Make sure we only include columns that exist
                    valid_columns = [col for col in column_order if col in results_df.columns]
                    
                    # Display the data
                    st.dataframe(results_df[valid_columns])
                    
                    # Store in session state for export button
                    st.session_state.results_df = results_df[valid_columns]
                    st.session_state.show_export = True
                except Exception as e:
                    st.error(f"Error reading database: {str(e)}")
        
        with col2:
            # Only show export button after viewing data
            if st.session_state.get('show_export', False):
                if st.button("Export to Excel"):
                    try:
                        # Create an Excel file in memory
                        excel_file = BytesIO()
                        st.session_state.results_df.to_excel(excel_file, index=False, engine='openpyxl')
                        excel_file.seek(0)
                        
                        # Create a timestamp for the filename
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        excel_filename = f"fab_flow_results_{timestamp}.xlsx"
                        
                        # Provide download button
                        st.download_button(
                            label="📥 Download Excel File",
                            data=excel_file,
                            file_name=excel_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Error exporting to Excel: {str(e)}")
    
    st.markdown("You may now close this window.")

# Excel export functionality has been integrated directly into the sidebar and thank you page
