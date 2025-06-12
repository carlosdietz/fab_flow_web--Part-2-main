import streamlit as st
import random
import plotly.graph_objects as go
import pandas as pd


st.set_page_config(page_title="Dice Game - Semiconductor Manufacturing Chain", layout="wide")

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
        stations[i].capacity = dice[i]
        stations[i].wip = len(stations[i].fifo)
        stations[i].throughput = min(stations[i].wip, stations[i].capacity)
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
        round_finished_units
    )

def get_tracked_avg_cycle_time(tracked_units):
    cycle_times = [v['exit'] - v['entry'] for v in tracked_units.values() if v['exit'] is not None]
    if cycle_times:
        return sum(cycle_times) / len(cycle_times)
    return 0

# --- Streamlit UI ---

if 'page' not in st.session_state:
    st.session_state.page = 'welcome'
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

# --- Welcome Page ---
if st.session_state.page == 'welcome':
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
    quiz_answers = st.session_state.quiz_answers
    for i, q in enumerate(quiz_questions):
        quiz_answers[i] = st.text_input(f"{i+1}. {q}", value=quiz_answers[i], key=f"quiz_{i}")
    if st.button("Submit Quiz"):
        if all(a.strip() for a in quiz_answers):
            st.session_state.quiz_submitted = True
            st.session_state.quiz_answers = quiz_answers
        else:
            st.warning("Please answer all questions!")
    if st.session_state.quiz_submitted:
        correct_answers = [
            "Expected Value of a Die Roll = (1+2+3+4+5+6)/6 = 3.5",
            "Estimates e.g. 70 finished Units after 20 rounds (20 * 3.5 = 70)",
            "A unit can pass through max. one station per round, so RPT is 10 with 10 stations.",
            "Estimates, but higher than 10, because of Waiting Times in Production Stations!"
        ]
        st.success("Quiz submitted! Here are the correct answers:")
        for i, q in enumerate(quiz_questions):
            st.markdown(f"**{i+1}. {q}**")
            st.markdown(f"Your answer: {quiz_answers[i]}")
            st.markdown(f"Correct: {correct_answers[i]}")
        if st.button("Start Game"):
            reset_game_state()
            st.session_state.page = 'initial'
            st.rerun()
# --- Game Board Page ---
elif st.session_state.page in ['initial', 'round']:
    if st.session_state.page == 'initial':
        reset_game_state()
        st.session_state.round_num = 1

    st.markdown(f"## Round {st.session_state.round_num}")

    # (Removed dice GIFs here)

    # Only process round if not already processed for this round
    if len(st.session_state.dice_history) < st.session_state.round_num:
        (
            st.session_state.prev_incoming,
            throughputs,
            dice,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units
        ) = process_round(
            st.session_state.stations,
            st.session_state.prev_incoming,
            st.session_state.dice_range_override if st.session_state.dice_range_override else DICE_RANGE,
            st.session_state.round_num,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            st.session_state.tracked_units
        )
        round_output = len(round_finished_units)
        st.session_state.round_outputs.append(round_output)
        st.session_state.dice_history.append(dice)
        st.session_state.throughputs_history.append(throughputs)
        st.session_state.end_wip_history.append(end_wip_per_step)
        st.session_state.total_end_wip_history.append(total_end_wip)
        st.session_state.round_finished_units_history.append(round_finished_units)
    else:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]

    # Always define dice, throughputs, end_wip_per_step, total_end_wip for the UI below
    if len(st.session_state.dice_history) >= st.session_state.round_num:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]
    else:
        # fallback to empty/defaults if not available
        dice = [1]*NUM_STEPS
        throughputs = [0]*NUM_STEPS
        end_wip_per_step = [0]*NUM_STEPS
        total_end_wip = 0

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
            try:
                st.image(f"images/dice{dice[i]}.png", width=30)
            except Exception:
                st.warning(f"Missing image: images/dice{dice[i]}.png")
            wip_count = s.wip if s.wip != RAW_MATERIAL else 999
            st.markdown(f"WIP: {wip_count if wip_count != 999 else '∞'}")
            # Only show wafer images if not Step 1 (i != 0) and WIP is not infinite
            if i != 0 and wip_count != 999:
                wafer_imgs = []
                for _ in range(min(wip_count, 10)):
                    wafer_imgs.append("images/wafer.png")
                if wafer_imgs:
                    st.image(wafer_imgs, width=20)
                st.caption("Wafers")
            elif i != 0:
                st.caption("Wafers")

    # KPI Panel
    st.markdown("---")
    st.markdown("### KPI Panel")
    total_output = sum(st.session_state.round_outputs)
    round_output = st.session_state.round_outputs[-1]
    total_wip = sum(e for e in end_wip_per_step[1:10] if isinstance(e, int))
    st.metric("Round Output", round_output)
    st.metric("Total Output", total_output)
    st.metric("Total WIP", total_wip)

    # Next round or end
    if st.session_state.round_num < NUM_ROUNDS:
        if st.button("Next Round"):
            st.session_state.round_num += 1
            st.session_state.page = 'round'
            st.rerun()
    else:
        if st.button("Show End Results"):
            st.session_state.page = 'end'
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
                round_finished_units
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
    st.session_state.round_num = 1  # <-- Add this line
    st.session_state.page = 'second_game_round'
    st.rerun()

elif st.session_state.page == 'second_game_round':
    st.markdown(f"## Second Game - Round {st.session_state.round_num}")

    # Only process round if not already processed for this round
    if len(st.session_state.dice_history) < st.session_state.round_num:
        (
            st.session_state.prev_incoming,
            throughputs,
            dice,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            end_wip_per_step,
            total_end_wip,
            round_finished_units
        ) = process_round(
            st.session_state.stations,
            st.session_state.prev_incoming,
            st.session_state.dice_range_override,
            st.session_state.round_num,
            st.session_state.finished_units,
            st.session_state.finished_cycles,
            st.session_state.tracked_units
        )
        round_output = len(round_finished_units)
        st.session_state.round_outputs.append(round_output)
        st.session_state.dice_history.append(dice)
        st.session_state.throughputs_history.append(throughputs)
        st.session_state.end_wip_history.append(end_wip_per_step)
        st.session_state.total_end_wip_history.append(total_end_wip)
        st.session_state.round_finished_units_history.append(round_finished_units)
    else:
        dice = st.session_state.dice_history[st.session_state.round_num-1]
        throughputs = st.session_state.throughputs_history[st.session_state.round_num-1]
        end_wip_per_step = st.session_state.end_wip_history[st.session_state.round_num-1]
        total_end_wip = st.session_state.total_end_wip_history[st.session_state.round_num-1]

    # Show stations as machines with wafers
    st.markdown("### Manufacturing Chain")
    floor_cols = st.columns(NUM_STEPS)
    for i, s in enumerate(st.session_state.stations):
        with floor_cols[i]:
            try:
                st.image("images/machine.png", width=60)
            except Exception:
                st.warning("Missing image: images/machine.png")
            st.markdown(f"**Step {i+1}**")
            try:
                st.image(f"images/dice{dice[i]}.png", width=30)
            except Exception:
                st.warning(f"Missing image: images/dice{dice[i]}.png")
            wip_count = s.wip if s.wip != RAW_MATERIAL else 999
            st.markdown(f"WIP: {wip_count if wip_count != 999 else '∞'}")
            wafer_imgs = []
            for _ in range(min(wip_count if wip_count != 999 else 10, 10)):
                try:
                    wafer_imgs.append("images/wafer.png")
                except Exception:
                    pass
            if wafer_imgs:
                st.image(wafer_imgs, width=20)
            st.caption("Wafers")
    st.markdown("---")
    st.markdown("### KPI Panel")
    total_output = sum(st.session_state.round_outputs)
    round_output = st.session_state.round_outputs[-1]
    total_wip = sum(e for e in end_wip_per_step[1:10] if isinstance(e, int))
    st.metric("Round Output", round_output)
    st.metric("Total Output", total_output)
    st.metric("Total WIP", total_wip)
    if st.session_state.round_num < NUM_ROUNDS:
        if st.button("Next Round"):
            st.session_state.round_num += 1
            st.session_state.page = 'second_game_round'
            st.rerun()
    else:
        if st.button("Show Comparison"):
            st.session_state.page = 'comparison'
            st.rerun()

# --- Comparison Page ---
elif st.session_state.page == 'comparison':
    st.markdown("## Comparison of Alternatives")
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
    st.markdown("You may now close this window.")