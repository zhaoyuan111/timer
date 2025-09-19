import streamlit as st
import datetime
from streamlit_autorefresh import st_autorefresh
import pandas as pd

st.set_page_config(page_title="When can I go HOME?", layout="centered")

# 自动刷新每秒
st_autorefresh(interval=1000, key="timer")

# 初始化 session state
if "events" not in st.session_state:
    st.session_state.events = []

# --- Sidebar: 设置 ---
st.sidebar.header("Settings")
enable_checkin = st.sidebar.checkbox("Enable check-in confirmation", value=True)

# --- Sidebar: 添加事件 ---
st.sidebar.header("Add Event")
event_name = st.sidebar.text_input("Event name", "Event A")
event_duration = st.sidebar.number_input("Duration (minutes)", min_value=1, value=1)
event_loops = st.sidebar.number_input("Number of loops", min_value=1, value=1)
elapsed_first = st.sidebar.number_input("Elapsed time for first loop (minutes)", min_value=0, value=0)
event_order = st.sidebar.number_input("Order (integer, events with same order run together)", min_value=0, value=0)
add_event = st.sidebar.button("Add event")

if add_event:
    now = datetime.datetime.now()
    remaining_first = max(event_duration - elapsed_first, 0)
    st.session_state.events.append({
        "name": event_name,
        "duration": event_duration,
        "loops": event_loops,
        "current_loop": 0,
        "next_time": now + datetime.timedelta(minutes=remaining_first) if event_loops > 0 else None,
        "waiting_confirm": False,
        "elapsed_first": elapsed_first,
        "order": event_order
    })

# --- 确保每个事件都有 order ---
for idx, ev in enumerate(st.session_state.events):
    if "order" not in ev:
        ev["order"] = idx

# --- 拖动调整顺序 ---
if st.session_state.events:
    df = pd.DataFrame([{
        "Order": ev["order"],
        "Name": ev["name"],
        "Duration(min)": ev["duration"],
        "Loops": ev["loops"]
    } for ev in st.session_state.events])
    st.sidebar.subheader("Reorder Events")
    edited = st.sidebar.data_editor(df, num_rows="dynamic", use_container_width=True)
    for i, ev in enumerate(st.session_state.events):
        ev["order"] = int(edited.loc[i, "Order"])
    st.session_state.events.sort(key=lambda x: x["order"])

# --- 计算总完成时间函数 ---
def compute_total_finish_time(events, now=None):
    if now is None:
        now = datetime.datetime.now()
    total_time = now

    # 按 order 排序
    orders = sorted(set(ev['order'] for ev in events))
    for order in orders:
        batch = [ev for ev in events if ev['order'] == order and ev['current_loop'] < ev['loops']]
        if not batch:
            continue

        # 批次最长剩余时间
        max_remaining_seconds = 0
        for ev in batch:
            remaining_loops = ev['loops'] - ev['current_loop']
            if remaining_loops <= 0:
                continue
            # 当前循环剩余时间
            remaining_current_loop = 0
            if ev["next_time"]:
                remaining_current_loop = max((ev["next_time"] - now).total_seconds(), 0)
            # 其他循环总时间
            remaining_other_loops = (remaining_loops - 1) * ev["duration"] * 60
            total_ev_seconds = remaining_current_loop + remaining_other_loops
            max_remaining_seconds = max(max_remaining_seconds, total_ev_seconds)

        # 批次结束时间 = 当前 total_time + max 剩余时间
        total_time = total_time + datetime.timedelta(seconds=max_remaining_seconds)

    return total_time

# --- Main page ---
st.title("⏳ When can I go HOME?")

if not st.session_state.events:
    st.info("Please add at least one event from the sidebar.")
else:
    now = datetime.datetime.now()

    # --- 找到当前最小 order 的活动事件 ---
    active_events = [ev for ev in st.session_state.events if ev['current_loop'] < ev['loops']]
    if active_events:
        min_order = min(ev['order'] for ev in active_events)
        current_batch = [ev for ev in active_events if ev['order'] == min_order]
    else:
        current_batch = []

    st.subheader("Event Status")

    # 遍历所有事件显示
    for i, ev in enumerate(st.session_state.events):
        st.markdown(f"### {ev['name']} (Order {ev['order']})")

        # 当前批次事件才激活倒计时
        if ev in current_batch:
            # 等待打卡确认
            if ev["waiting_confirm"] and enable_checkin:
                st.warning(f"⏰ Event '{ev['name']}' loop {ev['current_loop']}/{ev['loops']} finished. Please confirm.")
                if st.button(f"Confirm - {ev['name']}", key=f"confirm_{i}"):
                    ev["waiting_confirm"] = False
                    ev["current_loop"] += 1
                    if ev["current_loop"] < ev["loops"]:
                        ev["next_time"] = datetime.datetime.now() + datetime.timedelta(minutes=ev["duration"])
                    else:
                        ev["next_time"] = None
            else:
                remaining = (ev["next_time"] - now).total_seconds() if ev["next_time"] else None
                if remaining is not None and remaining > 0:
                    mins, secs = divmod(int(remaining), 60)
                    st.markdown(
                        f"<div style='font-size:32px; font-weight:bold; color:green;'>"
                        f"⏱ Remaining: {mins} min {secs} sec<br>"
                        f"(loop {ev['current_loop']+1}/{ev['loops']})</div>",
                        unsafe_allow_html=True
                    )
                    # 进度条
                    loop_total = ev["duration"] * 60
                    loop_elapsed = loop_total - remaining
                    progress = loop_elapsed / loop_total
                    st.progress(min(max(progress, 0), 1.0))
                else:
                    if enable_checkin:
                        ev["waiting_confirm"] = True
                        st.error("⏰ Time's up! Waiting for confirmation...")
                    else:
                        ev["current_loop"] += 1
                        if ev["current_loop"] < ev["loops"]:
                            ev["next_time"] = datetime.datetime.now() + datetime.timedelta(minutes=ev["duration"])
                        else:
                            ev["next_time"] = None

            # 跳过循环按钮
            if st.button(f"Skip loop - {ev['name']}", key=f"skip_{i}"):
                ev["waiting_confirm"] = False
                ev["current_loop"] += 1
                if ev["current_loop"] < ev["loops"]:
                    ev["next_time"] = datetime.datetime.now() + datetime.timedelta(minutes=ev["duration"])
                else:
                    ev["next_time"] = None
                st.info(f"⏭ Skipped one loop for {ev['name']}")
        else:
            # 非当前批次事件，只显示状态
            if ev["current_loop"] >= ev["loops"]:
                st.success("✅ All loops completed")
            else:
                st.info(f"⏳ Waiting to start (loop {ev['current_loop']}/{ev['loops']})")

    # --- 计算并显示总完成时间 ---
    total_finish_time = compute_total_finish_time(st.session_state.events, now)
    if total_finish_time:
        st.subheader("Estimated completion time for all events")
        st.markdown(
            f"<div style='font-size:28px; font-weight:bold; color:blue;'>{total_finish_time.strftime('%H:%M:%S')}</div>",
            unsafe_allow_html=True
        )




