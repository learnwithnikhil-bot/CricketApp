"""
Cricket Score Calculator App - V2 with Player Tracking
A free, user-friendly cricket scoring app built with Streamlit.
"""

import streamlit as st
import random
import string
import time
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
from PIL import Image, ImageDraw, ImageFont
import io

# Connect to Supabase (cached so it only connects once)
@st.cache_resource
def get_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

supabase = get_supabase()

# Page configuration
st.set_page_config(
    page_title="Cricket Score",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1e7e34;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #28a745, #20c997);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .stButton button {
        width: 100%;
        font-weight: bold;
        height: 3rem;
    }
    .striker-row {
        background-color: rgba(40, 167, 69, 0.15);
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #28a745;
    }
    .non-striker-row {
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #6c757d;
    }
    .scoreboard {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        border-radius: 14px;
        padding: 22px 26px;
        color: #ffffff;
        box-shadow: 0 4px 18px rgba(0,0,0,0.35);
        margin-bottom: 1rem;
    }
    .sb-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.95rem;
        letter-spacing: 0.5px;
        opacity: 0.85;
        text-transform: uppercase;
    }
    .sb-score {
        font-size: 3.4rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 6px 0 2px 0;
    }
    .sb-overs {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-bottom: 10px;
    }
    .sb-batsmen {
        display: flex;
        gap: 28px;
        font-size: 1rem;
        margin-top: 8px;
        flex-wrap: wrap;
    }
    .sb-bat-name { font-weight: 700; }
    .sb-divider {
        height: 1px;
        background: rgba(255,255,255,0.18);
        margin: 12px 0;
    }
    .sb-chase {
        font-size: 1rem;
        color: #ffd54f;
        font-weight: 600;
        margin-top: 6px;
    }
    .over-tracker {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: -8px;
        margin-bottom: 14px;
        flex-wrap: wrap;
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        border-radius: 0 0 14px 14px;
        padding: 4px 26px 18px 26px;
    }
    .over-label {
        font-size: 0.85rem;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 4px;
    }
    .ball {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.9rem;
        color: #fff;
    }
    .ball-dot { background: #6c757d; }
    .ball-run { background: #2e9e4f; }
    .ball-boundary { background: #1565c0; }
    .ball-wicket { background: #d32f2f; }
    .ball-extra { background: #f9a825; color: #222; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)


# Initialize session state
def init_session_state():
    defaults = {
        'setup_step': 'teams',  # 'teams', 'players', 'opening', 'playing'
        'team1_name': 'Team A',
        'team2_name': 'Team B',
        'total_overs': 6,
        'players_per_team': 11,
        'team1_players': [],
        'team2_players': [],
        'batting_team': 'Team A',
        'bowling_team': 'Team B',
        'runs': 0,
        'wickets': 0,
        'balls': 0,
        'extras': 0,
        'ball_history': [],
        'innings': 1,
        'team1_score': None,
        'team2_score': None,
        'target': None,
        'match_complete': False,
        'striker': None,
        'non_striker': None,
        'batsmen_stats': {},  # {player_name: {runs, balls, fours, sixes, out}}
        'next_batsman_index': 0,
        'awaiting_new_batsman': False,
        'current_bowler': None,
        'bowlers_stats': {},  # {bowler_name: {balls, runs, wickets, maidens, overs_bowled}}
        'awaiting_new_bowler': False,
        'over_runs': 0,  # Track runs in current over for maiden detection
        'consecutive_wides': 0,  # Track wides in a row for custom wide rule
        'toss_winner': None,  # Which team won the toss
        'toss_decision': None,  # 'Bat' or 'Bowl'
        'toss_done': False,  # Whether the coin has been flipped
        'match_code': None,  # Cloud match code for sharing
        'viewer_mode': False,  # True if this device is just watching, not scoring
        'last_save_time': 0.0,    # throttle: timestamp of last cloud save
        'pending_save': False,    # something changed but isn't saved yet
        'pending_no_ball': False, # waiting for user to pick runs off no ball
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


def calculate_overs(balls):
    """Convert balls into overs.balls format"""
    return f"{balls // 6}.{balls % 6}"


def calculate_run_rate(runs, balls):
    """Calculate current run rate"""
    if balls == 0:
        return 0.0
    overs = balls / 6
    return round(runs / overs, 2)


def calculate_required_run_rate(target, current_runs, total_overs, balls_bowled):
    """Calculate required run rate"""
    runs_needed = target - current_runs
    balls_remaining = (total_overs * 6) - balls_bowled
    if balls_remaining <= 0:
        return 0.0
    overs_remaining = balls_remaining / 6
    return round(runs_needed / overs_remaining, 2)


def get_strike_rate(runs, balls):
    """Calculate batsman's strike rate"""
    if balls == 0:
        return 0.0
    return round((runs / balls) * 100, 2)

def _load_font(size, bold=False):
    """Load a TTF font with graceful fallback to PIL default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _top_batter(batsmen_stats):
    if not batsmen_stats:
        return None
    name = max(batsmen_stats, key=lambda n: batsmen_stats[n].get('runs', 0))
    return name, batsmen_stats[name]


def _top_bowler(bowlers_stats):
    if not bowlers_stats:
        return None
    def key(n):
        s = bowlers_stats[n]
        balls = s.get('balls', 0)
        econ = (s.get('runs', 0) / (balls / 6)) if balls > 0 else 999
        return (s.get('wickets', 0), -econ)
    name = max(bowlers_stats, key=key)
    return name, bowlers_stats[name]


def generate_scorecard_image(t1, t2, result_text, total_overs):
    """Build a shareable PNG scorecard. Returns PNG bytes.

    Big bold scores, content auto-fit so nothing overflows, vertically
    centered so short matches fill the canvas."""
    W, H = 1080, 1080
    BG = (15, 32, 39)
    CARD = (30, 58, 68)
    ACCENT = (46, 158, 79)
    GOLD = (255, 213, 79)
    WHITE = (255, 255, 255)
    MUTED = (178, 196, 201)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = _load_font(100, bold=True)
    f_score = _load_font(148, bold=True)
    f_overs = _load_font(52)
    f_label = _load_font(44, bold=True)
    f_foot = _load_font(38)

    M = 60

    def _fit(text, base, max_w, bold=True, floor=18):
        sz = base
        while sz > floor:
            f = _load_font(sz, bold=bold)
            bb = d.textbbox((0, 0), text, font=f)
            if bb[2] - bb[0] <= max_w:
                return f
            sz -= 2
        return _load_font(floor, bold=bold)

    def center(text, font, y, fill=WHITE):
        bb = d.textbbox((0, 0), text, font=font)
        w = bb[2] - bb[0]
        d.text(((W - w) / 2, y), text, font=font, fill=fill)


    CARD_H = 330
    GAP = 36
    BANNER_H = 160
    title_h = 120
    block = title_h + 36 + CARD_H + GAP + CARD_H + 56 + BANNER_H
    y = (H - block) // 2


    center("MATCH RESULT", f_title, y, ACCENT)
    y += title_h + 36

    pad = 56
    xr = M + 560
    team_max_w = xr - (M + pad) - 20
    stat_max_w = (W - M) - xr - 30

    def card(score, top):
        d.rounded_rectangle([M, top, W - M, top + CARD_H], radius=30, fill=CARD)
        d.text((M + pad, top + 32), score['team'],
               font=_fit(score['team'], 88, team_max_w), fill=WHITE)
        d.text((M + pad, top + 130), f"{score['runs']}/{score['wickets']}",
               font=f_score, fill=GOLD)
        d.text((M + pad, top + 290), f"{score['overs']} / {total_overs} overs",
               font=f_overs, fill=MUTED)
        tb = _top_batter(score.get('batsmen_stats', {}))
        tw = _top_bowler(score.get('bowlers_stats', {}))

        if tb:
            n, s = tb
            txt = f"{n}  {s.get('runs', 0)} ({s.get('balls', 0)})"
            d.text((xr, top + 40), "TOP SCORER", font=f_label, fill=MUTED)
            d.text((xr, top + 100), txt, font=_fit(txt, 56, stat_max_w), fill=WHITE)
        if tw:
            n, s = tw
            bl = s.get('balls', 0)
            ov = f"{bl // 6}.{bl % 6}"
            txt = f"{n}  {s.get('wickets', 0)}/{s.get('runs', 0)} ({ov})"
            d.text((xr, top + 184), "BEST BOWLER", font=f_label, fill=MUTED)
            d.text((xr, top + 244), txt, font=_fit(txt, 56, stat_max_w), fill=WHITE)

    card(t1, y)
    y += CARD_H + GAP
    card(t2, y)
    y += CARD_H + 56

    d.rounded_rectangle([M, y, W - M, y + BANNER_H], radius=30, fill=ACCENT)
    rf = _fit(result_text, 62, (W - 2 * M) - 60)
    bb = d.textbbox((0, 0), result_text, font=rf)
    th = bb[3] - bb[1]
    center(result_text, rf, y + (BANNER_H - th) // 2 - bb[1], WHITE)

    center("Free Cricket Score App  -  built by Nikhil", f_foot, H - 46, MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_batting_team_players():
    """Get the list of players from the currently batting team"""
    if st.session_state.batting_team == st.session_state.team1_name:
        return st.session_state.team1_players
    return st.session_state.team2_players


def init_batsman_stats(player_name):
    """Initialize stats for a batsman"""
    if player_name not in st.session_state.batsmen_stats:
        st.session_state.batsmen_stats[player_name] = {
            'runs': 0,
            'balls': 0,
            'fours': 0,
            'sixes': 0,
            'out': False,
            'on_field': True,
        }

def get_bowling_team_players():
    """Get the list of players from the currently bowling team"""
    if st.session_state.bowling_team == st.session_state.team1_name:
        return st.session_state.team1_players
    return st.session_state.team2_players


def init_bowler_stats(player_name):
    """Initialize stats for a bowler"""
    if player_name not in st.session_state.bowlers_stats:
        st.session_state.bowlers_stats[player_name] = {
            'balls': 0,
            'runs': 0,
            'wickets': 0,
            'maidens': 0,
        }

def add_ball(runs_scored, is_wicket=False, extra_type=None):
    """Add a ball to the game"""


    if extra_type == 'Wide':
        st.session_state.consecutive_wides += 1
        runs_scored = 1 if st.session_state.consecutive_wides % 2 == 0 else 0
    elif extra_type == 'No Ball':
        # Batter can score off a no ball — caller passes the bat runs.
        st.session_state.consecutive_wides = 0
    else:
        st.session_state.consecutive_wides = 0

    ball_data = {
        'over': calculate_overs(st.session_state.balls),
        'runs': runs_scored,
        'wicket': is_wicket,
        'extra': extra_type,
        'striker': st.session_state.striker,
        'bowler': st.session_state.current_bowler,
    }


    bowler = st.session_state.current_bowler
    if bowler and bowler in st.session_state.bowlers_stats:
        st.session_state.bowlers_stats[bowler]['runs'] += runs_scored
        if extra_type not in ['Wide', 'No Ball']:
            st.session_state.bowlers_stats[bowler]['balls'] += 1
            st.session_state.over_runs += runs_scored
        else:
            st.session_state.over_runs += runs_scored
        if is_wicket:
            st.session_state.bowlers_stats[bowler]['wickets'] += 1

    st.session_state.runs += runs_scored


    striker = st.session_state.striker
    if striker and striker in st.session_state.batsmen_stats:
        if extra_type not in ['Wide', 'No Ball']:
            st.session_state.batsmen_stats[striker]['balls'] += 1
        if extra_type is None or extra_type == 'No Ball':
            # Credit batter for normal runs OR runs scored off a no ball.
            st.session_state.batsmen_stats[striker]['runs'] += runs_scored
            if runs_scored == 4:
                st.session_state.batsmen_stats[striker]['fours'] += 1
            elif runs_scored == 6:
                st.session_state.batsmen_stats[striker]['sixes'] += 1


    if extra_type in ['Wide', 'No Ball']:
        st.session_state.extras += 1
    else:
        st.session_state.balls += 1

    if is_wicket:
    
        st.session_state.wickets += 1
        if striker and striker in st.session_state.batsmen_stats:
            st.session_state.batsmen_stats[striker]['out'] = True
            st.session_state.batsmen_stats[striker]['on_field'] = False
        st.session_state.awaiting_new_batsman = True

   
    if not is_wicket and extra_type not in ['Wide', 'No Ball'] and runs_scored % 2 == 1:
        st.session_state.striker, st.session_state.non_striker = (
            st.session_state.non_striker, st.session_state.striker
        )

   
    if st.session_state.balls > 0 and st.session_state.balls % 6 == 0 and extra_type not in ['Wide', 'No Ball']:
   
        if st.session_state.over_runs == 0 and bowler:
            st.session_state.bowlers_stats[bowler]['maidens'] += 1
   
   
        st.session_state.over_runs = 0
        if not st.session_state.awaiting_new_batsman:
            st.session_state.striker, st.session_state.non_striker = (
                st.session_state.non_striker, st.session_state.striker
            )
      
        max_balls = st.session_state.total_overs * 6
        if st.session_state.balls < max_balls:
            st.session_state.awaiting_new_bowler = True

    st.session_state.ball_history.append(ball_data)


    max_balls = st.session_state.total_overs * 6
    batting_team_size = len(get_batting_team_players())

    if (st.session_state.balls >= max_balls or
            st.session_state.wickets >= batting_team_size - 1):
        end_innings()


    if (st.session_state.innings == 2 and
            st.session_state.target is not None and
            st.session_state.runs >= st.session_state.target):
        end_match()


def undo_last_ball():
    """Undo the last recorded ball"""
    if not st.session_state.ball_history:
        return

    last_ball = st.session_state.ball_history.pop()
    st.session_state.runs -= last_ball['runs']


    bowler = last_ball.get('bowler')
    if bowler and bowler in st.session_state.bowlers_stats:
        st.session_state.bowlers_stats[bowler]['runs'] -= last_ball['runs']
        if last_ball['extra'] not in ['Wide', 'No Ball']:
            st.session_state.bowlers_stats[bowler]['balls'] -= 1
        if last_ball['wicket']:
            st.session_state.bowlers_stats[bowler]['wickets'] -= 1


    striker = last_ball.get('striker')
    if striker and striker in st.session_state.batsmen_stats:
        if last_ball['extra'] not in ['Wide', 'No Ball']:
            st.session_state.batsmen_stats[striker]['balls'] -= 1
        if last_ball['extra'] is None:
            st.session_state.batsmen_stats[striker]['runs'] -= last_ball['runs']
            if last_ball['runs'] == 4:
                st.session_state.batsmen_stats[striker]['fours'] -= 1
            elif last_ball['runs'] == 6:
                st.session_state.batsmen_stats[striker]['sixes'] -= 1

    if last_ball['extra'] in ['Wide', 'No Ball']:
        st.session_state.extras -= 1
    else:
        st.session_state.balls -= 1

    if last_ball['wicket']:
        st.session_state.wickets -= 1
      
        if striker and striker in st.session_state.batsmen_stats:
            st.session_state.batsmen_stats[striker]['out'] = False
            st.session_state.batsmen_stats[striker]['on_field'] = True
        st.session_state.awaiting_new_batsman = False
        st.session_state.striker = striker


    count = 0
    for ball in reversed(st.session_state.ball_history):
        if ball['extra'] == 'Wide':
            count += 1
        else:
            break
    st.session_state.consecutive_wides = count


    st.session_state.awaiting_new_bowler = False


def end_innings():
    """End the current innings"""
    if st.session_state.innings == 1:
        st.session_state.team1_score = {
            'runs': st.session_state.runs,
            'wickets': st.session_state.wickets,
            'overs': calculate_overs(st.session_state.balls),
            'team': st.session_state.batting_team,
            'bowling_team': st.session_state.bowling_team,
            'batsmen_stats': dict(st.session_state.batsmen_stats),
            'bowlers_stats': dict(st.session_state.bowlers_stats),
        }  
        st.session_state.target = st.session_state.runs + 1
       
        if st.session_state.batting_team == st.session_state.team1_name:
            st.session_state.batting_team = st.session_state.team2_name
            st.session_state.bowling_team = st.session_state.team1_name
        else:
            st.session_state.batting_team = st.session_state.team1_name
            st.session_state.bowling_team = st.session_state.team2_name


        st.session_state.runs = 0
        st.session_state.wickets = 0
        st.session_state.balls = 0
        st.session_state.extras = 0
        st.session_state.ball_history = []
        st.session_state.innings = 2
        st.session_state.batsmen_stats = {}
        st.session_state.bowlers_stats = {}
        st.session_state.current_bowler = None
        st.session_state.awaiting_new_bowler = False
        st.session_state.over_runs = 0
        st.session_state.striker = None
        st.session_state.non_striker = None
        st.session_state.next_batsman_index = 0
        st.session_state.awaiting_new_batsman = False
        st.session_state.setup_step = 'opening'
    else:
        end_match()


def end_match():
    """End the match"""
    st.session_state.team2_score = {
        'runs': st.session_state.runs,
        'wickets': st.session_state.wickets,
        'overs': calculate_overs(st.session_state.balls),
        'team': st.session_state.batting_team,
        'bowling_team': st.session_state.bowling_team,
        'batsmen_stats': dict(st.session_state.batsmen_stats),
        'bowlers_stats': dict(st.session_state.bowlers_stats),
    }
    st.session_state.match_complete = True


def reset_match():
    """Reset the entire match"""x
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()

# ===== SUPABASE SAVE / LOAD =====

SAVE_KEYS = [
    'setup_step', 'team1_name', 'team2_name', 'total_overs', 'players_per_team',
    'team1_players', 'team2_players', 'batting_team', 'bowling_team', 'runs',
    'wickets', 'balls', 'extras', 'ball_history', 'innings', 'team1_score',
    'team2_score', 'target', 'match_complete', 'striker', 'non_striker',
    'batsmen_stats', 'next_batsman_index', 'awaiting_new_batsman',
    'current_bowler', 'bowlers_stats', 'awaiting_new_bowler', 'over_runs',
    'consecutive_wides', 'toss_winner', 'toss_decision', 'toss_done',
]


def generate_match_code():
    """Generate a short random match code like CRIC + 3 digits."""
    return "CRIC" + ''.join(random.choices(string.digits, k=3))


def build_state_dict():
    """Collect the current match state into a plain dict for saving."""
    return {key: st.session_state.get(key) for key in SAVE_KEYS}


def save_match_to_cloud():
    """Save (insert or update) the current match to Supabase."""
    if supabase is None:
        return False, "Cloud storage not configured."
    try:
        state = build_state_dict()
        code = st.session_state.get('match_code')
        if not code:
            return False, "No match code set."
        
        supabase.table('matches').upsert({
            'match_code': code,
            'state': state,
        }, on_conflict='match_code').execute()
        return True, "Saved!"
    except Exception as e:
        return False, f"Save failed: {e}"


def load_match_from_cloud(code):
    """Load a match by code and restore it into session_state."""
    if supabase is None:
        return False, "Cloud storage not configured."
    try:
        result = supabase.table('matches').select('state').eq('match_code', code).execute()
        if not result.data:
            return False, "Match code not found."
        state = result.data[0]['state']
        for key, value in state.items():
            st.session_state[key] = value
        st.session_state['match_code'] = code
        return True, "Loaded!"
    except Exception as e:
        return False, f"Load failed: {e}"

def auto_save(force=False):
    """Save to cloud, but throttled. Marks state dirty and only pushes to
    Supabase every few seconds or when force=True (over end, wicket, innings,
    match). ball_history in session_state is always the live source of truth,
    so nothing is lost between throttled saves."""
    if not st.session_state.get('match_code') or st.session_state.get('viewer_mode'):
        return
    if supabase is None:
        return

    st.session_state.pending_save = True
    now = time.time()
    SAVE_INTERVAL = 8  # seconds between routine saves

    if force or (now - st.session_state.get('last_save_time', 0) >= SAVE_INTERVAL):
        ok, _ = save_match_to_cloud()
        if ok:
            st.session_state.last_save_time = now
            st.session_state.pending_save = False

def get_current_over_balls():
    """Return the deliveries belonging to the current (or just-completed) over."""
    history = st.session_state.ball_history
    total_balls = st.session_state.balls
    legal_in_current = total_balls % 6

    if legal_in_current == 0 and total_balls > 0:
        legal_target = 6
    else:
        legal_target = legal_in_current

    collected = []
    legal_seen = 0
    for ball in reversed(history):
        is_legal = ball['extra'] not in ['Wide', 'No Ball']
        if is_legal:
            if legal_seen >= legal_target:
                break
            legal_seen += 1
        collected.append(ball)
    collected.reverse()
    return collected


def render_over_tracker():
    """Build the HTML for the this-over ball tracker."""
    balls = get_current_over_balls()
    if not balls:
        return ""

    chips = []
    for ball in balls:
        if ball['wicket']:
            chips.append('<div class="ball ball-wicket">W</div>')
        elif ball['extra'] == 'Wide':
            chips.append('<div class="ball ball-extra">WD</div>')
        elif ball['extra'] == 'No Ball':
            chips.append('<div class="ball ball-extra">NB</div>')
        elif ball['runs'] == 0:
            chips.append('<div class="ball ball-dot">•</div>')
        elif ball['runs'] in (4, 6):
            chips.append(f'<div class="ball ball-boundary">{ball["runs"]}</div>')
        else:
            chips.append(f'<div class="ball ball-run">{ball["runs"]}</div>')

    return (
        '<div class="over-tracker">'
        '<span class="over-label">This over:</span>'
        + ''.join(chips) +
        '</div>'
    )

# Header
st.markdown('<div class="main-header">🏏 Cricket Score</div>',
            unsafe_allow_html=True)

# ============ SETUP STEP 1: TEAMS ============
if st.session_state.setup_step == 'teams':
    st.subheader("⚙️ Step 1: Match Setup")

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.team1_name = st.text_input(
            "Team 1 Name", value=st.session_state.team1_name)
    with col2:
        st.session_state.team2_name = st.text_input(
            "Team 2 Name", value=st.session_state.team2_name)

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.total_overs = st.number_input(
            "Total Overs", min_value=1, max_value=50,
            value=st.session_state.total_overs)
    with col2:
        st.session_state.players_per_team = st.number_input(
            "Players per Team", min_value=2, max_value=15,
            value=st.session_state.players_per_team)

    if st.button("➡️ Next: Coin Toss", type="primary"):
        st.session_state.setup_step = 'toss'
        st.rerun()


    st.markdown("---")
    st.markdown("#### 📲 Or load a saved match")
    load_code = st.text_input("Enter Match Code (e.g. CRIC123)", key="load_code_input").strip().upper()
    if st.button("📥 Load Match"):
        if load_code:
            ok, msg = load_match_from_cloud(load_code)
            if ok:
                st.session_state.viewer_mode = True
                st.success(f"Loaded match {load_code}!")
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("Please enter a match code.")

# ============ SETUP STEP: COIN TOSS ============
elif st.session_state.setup_step == 'toss':
    st.subheader("🪙 Coin Toss")

    if not st.session_state.toss_done:
        st.markdown(f"### {st.session_state.team1_name}  🆚  {st.session_state.team2_name}")
        
        st.markdown("""
        <style>
            @keyframes floaty {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-12px); }
            }
            .coin-static {
                text-align: center;
                font-size: 6rem;
                animation: floaty 2s ease-in-out infinite;
            }
        </style>
        <div class="coin-static">🪙</div>
        """, unsafe_allow_html=True)
        st.info("Click the button below to flip the coin!")

        if st.button("🪙 Flip the Coin!", type="primary"):
            winner = random.choice([st.session_state.team1_name, st.session_state.team2_name])
            st.session_state.toss_winner = winner
            st.session_state.toss_done = True
            st.rerun()
    else:
       
        st.markdown("""
        <style>
            @keyframes flip-spin {
                0%   { transform: rotateY(0deg) scale(1); }
                100% { transform: rotateY(1800deg) scale(1); }
            }
            .coin-flip {
                text-align: center;
                font-size: 6rem;
                animation: flip-spin 1.2s ease-out;
            }
        </style>
        <div class="coin-flip">🪙</div>
        """, unsafe_allow_html=True)
        st.success(f"🎉 **{st.session_state.toss_winner}** won the toss!")
        st.markdown(f"**{st.session_state.toss_winner}**, what would you like to do?")

        decision = st.radio("Choose:", ["Bat", "Bowl"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Re-flip Coin"):
                st.session_state.toss_done = False
                st.session_state.toss_winner = None
                st.rerun()
        with col2:
            if st.button("➡️ Next: Add Players", type="primary"):
                st.session_state.toss_decision = decision
              
                if decision == "Bat":
                    st.session_state.batting_team = st.session_state.toss_winner
                else:
              
                    st.session_state.batting_team = (
                        st.session_state.team2_name
                        if st.session_state.toss_winner == st.session_state.team1_name
                        else st.session_state.team1_name
                    )
                st.session_state.bowling_team = (
                    st.session_state.team2_name
                    if st.session_state.batting_team == st.session_state.team1_name
                    else st.session_state.team1_name
                )
                st.session_state.setup_step = 'players'
                st.rerun()

# ============ SETUP STEP 2: PLAYERS ============
elif st.session_state.setup_step == 'players':
    st.subheader("👥 Step 2: Add Players")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### 🏏 {st.session_state.team1_name}")
        team1_players_input = []
        for i in range(st.session_state.players_per_team):
            default_name = (
                st.session_state.team1_players[i]
                if i < len(st.session_state.team1_players)
                else f"Player {i+1}"
            )
            name = st.text_input(f"Player {i+1}", value=default_name, key=f"t1_player_{i}")
            team1_players_input.append(name)

    with col2:
        st.markdown(f"### 🏏 {st.session_state.team2_name}")
        team2_players_input = []
        for i in range(st.session_state.players_per_team):
            default_name = (
                st.session_state.team2_players[i]
                if i < len(st.session_state.team2_players)
                else f"Player {i+1}"
            )
            name = st.text_input(f"Player {i+1}", value=default_name, key=f"t2_player_{i}")
            team2_players_input.append(name)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back to Teams"):
            st.session_state.setup_step = 'teams'
            st.session_state.toss_done = False
            st.session_state.toss_winner = None
            st.session_state.toss_decision = None
            st.rerun()
    with col2:
        if st.button("➡️ Next: Choose Openers", type="primary"):
            st.session_state.team1_players = team1_players_input
            st.session_state.team2_players = team2_players_input
            st.session_state.setup_step = 'opening'
            st.rerun()

# ============ SETUP STEP 3: OPENING BATSMEN ============
elif st.session_state.setup_step == 'opening':
    if st.session_state.innings == 1:
        st.subheader("🎯 Choose Opening Players")
        st.success(
            f"🪙 {st.session_state.toss_winner} won the toss and chose to "
            f"{st.session_state.toss_decision.lower()}."
        )
    else:
        st.subheader(f"🎯 Innings 2: Choose Opening Batsmen for {st.session_state.batting_team}")
        st.info(f"Target: **{st.session_state.target}** runs in {st.session_state.total_overs} overs")

    batting_players = get_batting_team_players()
   
    st.markdown(f"**Batting Team: {st.session_state.batting_team}**")

    col1, col2 = st.columns(2)
    with col1:
        striker = st.selectbox("🏏 Striker (on strike)", batting_players, index=0)
    with col2:
        non_striker_options = [p for p in batting_players if p != striker]
        non_striker = st.selectbox("🏃 Non-Striker", non_striker_options, index=0)

    bowling_players = get_bowling_team_players()
    opening_bowler = st.selectbox("⚾ Opening Bowler", bowling_players, index=0)

    if st.button("🚀 Start Match!", type="primary"):
        st.session_state.striker = striker
        st.session_state.non_striker = non_striker
        st.session_state.current_bowler = opening_bowler
        init_batsman_stats(striker)
        init_batsman_stats(non_striker)
        init_bowler_stats(opening_bowler)
       
        st.session_state.next_batsman_index = 2
        st.session_state.setup_step = 'playing'
        st.rerun()

# ============ MATCH COMPLETE ============
elif st.session_state.match_complete:
    st.balloons()
    st.header("🏆 Match Complete!")

    t1 = st.session_state.team1_score
    t2 = st.session_state.team2_score

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {t1['team']}")
        st.markdown(f"## {t1['runs']}/{t1['wickets']}")
      
        st.markdown(f"**Overs:** {t1['overs']}")
    with col2:
        st.markdown(f"### {t2['team']}")
        st.markdown(f"## {t2['runs']}/{t2['wickets']}")
        st.markdown(f"**Overs:** {t2['overs']}")

    st.markdown("---")

    # Determine winner (capture result_text for the shareable image)
    if t1['runs'] > t2['runs']:
        margin = t1['runs'] - t2['runs']
        result_text = f"{t1['team']} won by {margin} runs!"
        st.success(f"🎉 **{result_text}**")
    elif t2['runs'] > t1['runs']:
        wickets_left = (st.session_state.players_per_team - 1) - t2['wickets']
        result_text = f"{t2['team']} won by {wickets_left} wickets!"
        st.success(f"🎉 **{result_text}**")
    else:
        result_text = "Match Tied!"
        st.warning(f"🤝 **{result_text}**")

    # ===== SHAREABLE SCORECARD IMAGE =====
    st.markdown("---")
    st.subheader("📸 Share this result")
    try:
        img_bytes = generate_scorecard_image(
            t1, t2, result_text, st.session_state.total_overs
        )
        st.image(img_bytes, caption="Your shareable scorecard", width=400)
        st.download_button(
            "⬇️ Download scorecard image",
            data=img_bytes,
            file_name=f"{t1['team']}_vs_{t2['team']}_scorecard.png",
            mime="image/png",
            type="primary",
        )
        st.caption("Save it and post to your WhatsApp group! 🏏")
    except Exception as e:
        st.warning(f"Couldn't generate the scorecard image: {e}")

    st.markdown("---")
    st.subheader("📊 Full Scorecards")

    for innings_score in [t1, t2]:
        st.markdown(f"### {innings_score['team']} - {innings_score['runs']}/{innings_score['wickets']} ({innings_score['overs']} overs)")


        st.markdown("**🏏 Batting**")
        if innings_score.get('batsmen_stats'):
            data = []
            for name, stats in innings_score['batsmen_stats'].items():
                status = "out" if stats['out'] else "not out"
                sr = get_strike_rate(stats['runs'], stats['balls'])
                data.append({
                    'Batsman': name, 'Status': status, 'Runs': stats['runs'],
                    'Balls': stats['balls'], '4s': stats['fours'],
                    '6s': stats['sixes'], 'SR': sr,
                })
            st.dataframe(data, use_container_width=True, hide_index=True)


        bowling_team_name = innings_score.get('bowling_team', 'Bowling Team')
        st.markdown(f"**⚾ Bowling ({bowling_team_name})**")
        if innings_score.get('bowlers_stats'):
            bowl_data = []
            for name, stats in innings_score['bowlers_stats'].items():
                overs_str = f"{stats['balls'] // 6}.{stats['balls'] % 6}"
                econ = round((stats['runs'] / (stats['balls'] / 6)), 2) if stats['balls'] > 0 else 0.0
                bowl_data.append({
                    'Bowler': name, 'Overs': overs_str, 'Runs': stats['runs'],
                    'Wickets': stats['wickets'], 'Maidens': stats['maidens'], 'Econ': econ,
                })
            st.dataframe(bowl_data, use_container_width=True, hide_index=True)
        else:
            st.info("No bowling stats recorded")

        st.markdown("---")

    if st.button("🆕 Start New Match", type="primary"):
        reset_match()
        st.rerun()

# ============ ACTIVE MATCH - SCORING ============
elif st.session_state.setup_step == 'playing':

    # ===== VIEWER MODE: auto-refresh and reload from cloud =====
    if st.session_state.get('viewer_mode') and st.session_state.get('match_code'):
      
        st_autorefresh(interval=10000, key="viewer_refresh")
      
        load_match_from_cloud(st.session_state.match_code)
      
        st.session_state.viewer_mode = True
        st.info("👁️ **Viewing Mode** — auto-updates every 10 seconds. You cannot score in this mode.")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Match Info")
        st.success(f"**{st.session_state.team1_name}** vs **{st.session_state.team2_name}**")
        st.info(f"Format: {st.session_state.total_overs} overs")
        st.info(f"Innings: {st.session_state.innings}/2")
        st.info(f"Batting: {st.session_state.batting_team}")
        st.info(f"Bowling: {st.session_state.bowling_team}")
        if st.session_state.toss_winner:
            st.caption(
                f"🪙 {st.session_state.toss_winner} won the toss & chose to "
                f"{st.session_state.toss_decision.lower()}"
            )

        st.markdown("---")

        # ===== CLOUD SAVE / SHARE =====
        st.markdown("### ☁️ Cloud Save")
        if supabase is None:
            st.caption("⚠️ Cloud storage not configured")
        elif not st.session_state.get('match_code'):
            if st.button("💾 Save & Get Code"):
                st.session_state.match_code = generate_match_code()
                ok, msg = save_match_to_cloud()
                if ok:
                    st.session_state.last_save_time = time.time()
                    st.session_state.pending_save = False
                    st.success(f"Saved! Code: {st.session_state.match_code}")
                else:
                    st.error(msg)
                    st.session_state.match_code = None
                st.rerun()
        else:
            st.success(f"Match Code: **{st.session_state.match_code}**")
            if st.session_state.get('pending_save'):
                st.caption("🟡 Recent balls saved locally — syncing…")
            else:
                st.caption("✅ All balls synced to the cloud.")
            st.caption("Share this code so others can follow live.")
            if st.button("💾 Force Save Now"):
                ok, msg = save_match_to_cloud()
                if ok:
                    st.session_state.last_save_time = time.time()
                    st.session_state.pending_save = False
                    st.success("Saved!")
                else:
                    st.error(msg)

        st.markdown("---")
        if st.button("🔄 Reset Match"):
            reset_match()
            st.rerun()

    # ===== BROADCAST SCOREBOARD =====
    crr = calculate_run_rate(st.session_state.runs, st.session_state.balls)
    striker = st.session_state.striker
    non_striker = st.session_state.non_striker
    s_stats = st.session_state.batsmen_stats.get(striker, {})
    ns_stats = st.session_state.batsmen_stats.get(non_striker, {})


    chase_html = ""
    if st.session_state.innings == 2 and st.session_state.target:
        runs_needed = max(0, st.session_state.target - st.session_state.runs)
        balls_remaining = max(0, (st.session_state.total_overs * 6) - st.session_state.balls)
        rrr = calculate_required_run_rate(
            st.session_state.target, st.session_state.runs,
            st.session_state.total_overs, st.session_state.balls
        )
        chase_html = (
            f"<div class='sb-chase'>🎯 Need {runs_needed} runs from {balls_remaining} balls "
            f"&nbsp;·&nbsp; Req. RR {rrr}</div>"
        )

    scoreboard_html = f"""
    <div class="scoreboard">
        <div class="sb-top">
            <span>🏏 {st.session_state.batting_team} — batting</span>
            <span>Innings {st.session_state.innings}/2</span>
        </div>
        <div class="sb-score">{st.session_state.runs}-{st.session_state.wickets}</div>
        <div class="sb-overs">
            {calculate_overs(st.session_state.balls)} / {st.session_state.total_overs} overs
            &nbsp;·&nbsp; CRR {crr}
        </div>
        <div class="sb-divider"></div>
        <div class="sb-batsmen">
            <span><span class="sb-bat-name">🏏 {striker} *</span>
                &nbsp;{s_stats.get('runs', 0)} ({s_stats.get('balls', 0)})</span>
            <span><span class="sb-bat-name">{non_striker}</span>
                &nbsp;{ns_stats.get('runs', 0)} ({ns_stats.get('balls', 0)})</span>
        </div>
        {chase_html}
    </div>
    """
    st.markdown(scoreboard_html, unsafe_allow_html=True)


    tracker_html = render_over_tracker()
    if tracker_html:
        st.markdown(tracker_html, unsafe_allow_html=True)

    # ===== CURRENT BOWLER =====
    st.subheader("⚾ Current Bowler")

    if st.session_state.awaiting_new_bowler:
        st.warning("⚠️ End of over! Select the next bowler.")
        bowling_players = get_bowling_team_players()
      
        available_bowlers = [p for p in bowling_players if p != st.session_state.current_bowler]
        new_bowler = st.selectbox("Select next bowler:", available_bowlers, key="new_bowler_select")
        if st.button("✅ Confirm New Bowler", type="primary"):
            st.session_state.current_bowler = new_bowler
            init_bowler_stats(new_bowler)
            st.session_state.awaiting_new_bowler = False
            auto_save(force=True)
            st.rerun()
    else:
        bowler = st.session_state.current_bowler
        b_stats = st.session_state.bowlers_stats.get(bowler, {})
        overs_bowled = f"{b_stats.get('balls', 0) // 6}.{b_stats.get('balls', 0) % 6}"
        econ = round((b_stats.get('runs', 0) / (b_stats.get('balls', 0) / 6)), 2) if b_stats.get('balls', 0) > 0 else 0.0
        st.info(
            f"**⚾ {bowler}** | Overs: **{overs_bowled}** | "
            f"Runs: **{b_stats.get('runs', 0)}** | "
            f"Wickets: **{b_stats.get('wickets', 0)}** | "
            f"Maidens: **{b_stats.get('maidens', 0)}** | "
            f"Econ: **{econ}**"
        )

    st.markdown("---")

    # ===== BATSMEN ON FIELD =====
    st.subheader("🏏 Batsmen on Field")


    if st.session_state.awaiting_new_batsman:
        st.warning("⚠️ Wicket fallen! Select the next batsman.")
        batting_players = get_batting_team_players()
        available_batsmen = [
            p for p in batting_players
            if p != st.session_state.non_striker
            and (p not in st.session_state.batsmen_stats
                 or not st.session_state.batsmen_stats[p]['out'])
        ]

        if available_batsmen:
            new_batsman = st.selectbox("Select new batsman:", available_batsmen)
            if st.button("✅ Confirm New Batsman", type="primary"):
                st.session_state.striker = new_batsman
                init_batsman_stats(new_batsman)
                st.session_state.awaiting_new_batsman = False
                auto_save(force=True)
                st.rerun()
        else:
            st.error("No more batsmen available - innings should end")
    else:
      
        striker_stats = st.session_state.batsmen_stats.get(st.session_state.striker, {})
        non_striker_stats = st.session_state.batsmen_stats.get(st.session_state.non_striker, {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="striker-row">
            <strong>🏏 {st.session_state.striker} *</strong> (on strike)<br>
            Runs: <b>{striker_stats.get('runs', 0)}</b> ({striker_stats.get('balls', 0)} balls)<br>
            4s: {striker_stats.get('fours', 0)} | 6s: {striker_stats.get('sixes', 0)} |
            SR: {get_strike_rate(striker_stats.get('runs', 0), striker_stats.get('balls', 0))}
            </div>
            """, unsafe_allow_html=True)
      
        with col2:
            st.markdown(f"""
            <div class="non-striker-row">
            <strong>🏃 {st.session_state.non_striker}</strong> (non-striker)<br>
            Runs: <b>{non_striker_stats.get('runs', 0)}</b> ({non_striker_stats.get('balls', 0)} balls)<br>
            4s: {non_striker_stats.get('fours', 0)} | 6s: {non_striker_stats.get('sixes', 0)} |
            SR: {get_strike_rate(non_striker_stats.get('runs', 0), non_striker_stats.get('balls', 0))}
            </div>
            """, unsafe_allow_html=True)


        if st.button("🔄 Swap Strike"):
            st.session_state.striker, st.session_state.non_striker = (
                st.session_state.non_striker, st.session_state.striker
            )
            auto_save()
            st.rerun()

    st.markdown("---")

    # Scoring buttons (hidden in viewer mode)
    if (not st.session_state.awaiting_new_batsman
            and not st.session_state.awaiting_new_bowler
            and not st.session_state.get('viewer_mode')
            and st.session_state.get('pending_no_ball')):
        # ===== NO BALL: pick bat runs =====
        st.warning("⚾ **No Ball!** How many runs off the bat?")
        nb_cols = st.columns(7)
        for i, runs in enumerate([0, 1, 2, 3, 4, 5, 6]):
            with nb_cols[i]:
                label = f"NB + {runs}"
                if st.button(label, key=f"nb_runs_{runs}"):
                    st.session_state.pending_no_ball = False
                    add_ball(runs, extra_type='No Ball')
                    auto_save()
                    st.rerun()
        if st.button("❌ Cancel No Ball"):
            st.session_state.pending_no_ball = False
            st.rerun()

    elif (not st.session_state.awaiting_new_batsman
            and not st.session_state.awaiting_new_bowler
            and not st.session_state.get('viewer_mode')):
        st.subheader("📝 Add Score")

        st.markdown("**Runs Scored:**")
        cols = st.columns(7)
        run_options = [0, 1, 2, 3, 4, 5, 6]
        for i, runs in enumerate(run_options):
            with cols[i]:
                label = f"{runs} Run" if runs <= 1 else f"{runs} Runs"
                if runs == 4:
                    label = "4️⃣ FOUR"
                elif runs == 6:
                    label = "6️⃣ SIX"
                if st.button(label, key=f"run_{runs}"):
                    add_ball(runs)
                    auto_save()
                    st.rerun()

        st.markdown("**Special:**")
       
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🎯 WICKET", type="primary"):
                add_ball(0, is_wicket=True)
                auto_save(force=True)
                st.rerun()
        with col2:
            if st.button("Wide"):
                add_ball(0, extra_type='Wide')
                auto_save()
                st.rerun()
        with col3:
            if st.button("No Ball"):
                st.session_state.pending_no_ball = True
                st.rerun()
        with col4:
            if st.button("↩️ UNDO"):
                undo_last_ball()
                auto_save()
                st.rerun()


        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏁 End Innings"):
                end_innings()
                auto_save(force=True)
                st.rerun()
        with col2:
            if st.button("🛑 End Match"):
                end_match()
                auto_save(force=True)
                st.rerun()

    # ===== BOWLING SCORECARD =====
    st.subheader("⚾ Bowling Figures")
    if st.session_state.bowlers_stats:
        bowling_data = []
        for name, stats in st.session_state.bowlers_stats.items():
            overs_str = f"{stats['balls'] // 6}.{stats['balls'] % 6}"
            econ = round((stats['runs'] / (stats['balls'] / 6)), 2) if stats['balls'] > 0 else 0.0
            bowling_data.append({
                'Bowler': name, 'Overs': overs_str, 'Runs': stats['runs'],
                'Wickets': stats['wickets'], 'Maidens': stats['maidens'], 'Econ': econ,
            })
        st.dataframe(bowling_data, use_container_width=True, hide_index=True)
    else:
        st.info("No bowling stats yet")

    # ===== SCORECARD =====
    st.markdown("---")
    st.subheader("📊 Batting Scorecard")


    if st.session_state.batsmen_stats:
        scorecard_data = []
        for name, stats in st.session_state.batsmen_stats.items():
            if stats['out']:
                status = "out"
            elif name == st.session_state.striker:
                status = "batting *"
            elif name == st.session_state.non_striker:
                status = "batting"
            else:
                status = "-"
         
            sr = get_strike_rate(stats['runs'], stats['balls'])
            scorecard_data.append({
                'Batsman': name, 'Status': status, 'Runs': stats['runs'],
                'Balls': stats['balls'], '4s': stats['fours'],
                '6s': stats['sixes'], 'SR': sr,
            })
        st.dataframe(scorecard_data, use_container_width=True, hide_index=True)
    else:
        st.info("No batting stats yet")


    if st.session_state.ball_history:
        with st.expander("📜 Recent Balls"):
            recent_balls = st.session_state.ball_history[-12:]
            for ball in reversed(recent_balls):
                entry = f"Over {ball['over']}: {ball.get('striker', '?')} - {ball['runs']} run(s)"
                if ball['wicket']:
                    entry += " 🎯 WICKET"
                if ball['extra']:
                    entry += f" ({ball['extra']})"
                st.text(entry)


    if st.session_state.innings == 2 and st.session_state.team1_score:
        with st.expander("📊 First Innings Summary"):
            t1 = st.session_state.team1_score
            st.info(f"**{t1['team']}**: {t1['runs']}/{t1['wickets']} in {t1['overs']} overs")
            if t1.get('batsmen_stats'):
                data = []
                for name, stats in t1['batsmen_stats'].items():
                    status = "out" if stats['out'] else "not out"
                    data.append({
                        'Batsman': name, 'Status': status, 'Runs': stats['runs'],
                        'Balls': stats['balls'], '4s': stats['fours'],
                        '6s': stats['sixes'],
                        'SR': get_strike_rate(stats['runs'], stats['balls']),
                    })
                st.dataframe(data, use_container_width=True, hide_index=True)


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "Built by Nikhil with ❤️ | Free to use forever 🏏"
    "</div>",
    unsafe_allow_html=True
)
