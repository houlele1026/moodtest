import json
import os
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, flash, redirect, render_template, request, session, url_for


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "model_config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config" / "model_config.example.json"
EPISODES_PATH = ROOT / "data" / "pilot_episodes_v1.json"
SYSTEM_PROMPT_PATH = ROOT / "docs" / "system_prompt.md"
ACTIVE_SESSIONS_DIR = ROOT / "storage" / "active_sessions"
LOGS_DIR = ROOT / "storage" / "logs"

ACTIVE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SESSION_RATING_FIELDS = [
    ("felt_understood", "我感到自己被理解了。"),
    ("natural_empathy", "模型的共情表达是自然的。"),
    ("matched_current_need", "模型的回应符合我当下真正需要。"),
    ("low_template_feeling", "模型的回复没有明显模板感。"),
    ("natural_history_usage", "模型对历史信息的利用是自然的。"),
    ("willing_to_continue", "我愿意继续和这个模型聊下去。"),
    ("non_preachy", "模型没有明显说教或居高临下。"),
    ("overall_supportiveness", "这一整次 session 让我感到被支持。"),
]

EPISODE_RATING_FIELDS = [
    ("continuity_across_sessions", "这个模型在 3 个 session 之间表现出了连续感。"),
    ("emotional_stability", "这个模型的情绪支持质量是稳定的。"),
    ("trust", "和它聊这个问题时，我逐渐建立了信任感。"),
    ("repair_ability", "当我表现出迟疑、失望或轻度质疑时，它有一定修复能力。"),
    ("overall_companionship_quality", "总体来看，它提供了较好的长期陪伴体验。"),
]

SCORE_LABELS = {
    "1": "非常不同意",
    "2": "不同意",
    "3": "一般",
    "4": "同意",
    "5": "非常同意",
}


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write(text)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_app_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
      return load_json(CONFIG_PATH)
    return load_json(CONFIG_EXAMPLE_PATH)


def load_episodes() -> Dict[str, Any]:
    return load_json(EPISODES_PATH)


def extract_system_prompt(markdown_text: str) -> str:
    if "```text" in markdown_text:
        start = markdown_text.index("```text") + len("```text")
        end = markdown_text.index("```", start)
        return markdown_text[start:end].strip()
    return markdown_text.strip()


def load_system_prompt() -> str:
    with SYSTEM_PROMPT_PATH.open("r", encoding="utf-8") as file:
        return extract_system_prompt(file.read())


def get_episode(episode_id: str) -> Dict[str, Any]:
    for episode in load_episodes()["episodes"]:
        if episode["episode_id"] == episode_id:
            return episode
    raise ValueError(f"未找到 episode: {episode_id}")


def get_session_brief(episode: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    for session_item in episode["sessions"]:
        if session_item["session_id"] == session_id:
            return session_item
    raise ValueError(f"未找到 session: {session_id}")


def get_model_config(blind_id: str) -> Dict[str, Any]:
    config = load_app_config()
    for model in config["models"]:
        if model["blind_id"] == blind_id:
            return model
    raise ValueError(f"未找到模型 blind_id={blind_id}")


def sanitize_model_config(model_config: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = deepcopy(model_config)
    snapshot.pop("api_key", None)
    snapshot.pop("api_key_env", None)
    return snapshot


def resolve_api_key(model_config: Dict[str, Any]) -> str:
    if model_config.get("api_key"):
        return model_config["api_key"]
    env_name = model_config.get("api_key_env")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    raise ValueError(
        f"模型 {model_config.get('blind_id', '<unknown>')} 未找到可用 API Key。"
        f"如果你使用环境变量，请确认已设置 {env_name}。"
    )


def create_client(model_config: Dict[str, Any]):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("当前环境未安装 openai 包，请先安装依赖。") from exc

    return OpenAI(
        api_key=resolve_api_key(model_config),
        base_url=model_config.get("base_url"),
    )


def chat_once(client, model_config: Dict[str, Any], messages: List[Dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model=model_config["model_identifier"],
        messages=messages,
        **deepcopy(model_config.get("generation_kwargs", {})),
    )
    return response.choices[0].message.content or ""


def create_state_path(run_id: str) -> Path:
    return ACTIVE_SESSIONS_DIR / f"{run_id}.json"


def render_transcript(conversation: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    lines = [
        "# Session Transcript",
        "",
        f"- tester_id: {metadata['tester_id']}",
        f"- episode_id: {metadata['episode_id']}",
        f"- session_id: {metadata['session_id']}",
        f"- model_blind_id: {metadata['model_blind_id']}",
        f"- started_at: {metadata['started_at']}",
        f"- ended_at: {metadata['ended_at']}",
        "",
        "## Conversation",
        "",
    ]
    pending_user = None
    turn = 0
    for item in conversation:
        if item["role"] == "user":
            pending_user = item["content"]
            turn += 1
        elif item["role"] == "assistant":
            lines.extend([
                f"### Turn {turn}",
                "User:",
                pending_user or "",
                "",
                "Assistant:",
                item["content"],
                "",
            ])
            pending_user = None
    return "\n".join(lines)


def build_log_dir(tester_id: str, episode_id: str, session_id: str, model_blind_id: str) -> Path:
    path = LOGS_DIR / f"tester_{tester_id}" / episode_id / session_id / model_blind_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_blank_rating(template_name: str, tester_id: str, episode_id: str, session_id: str, model_blind_id: str, part_type: str) -> Dict[str, Any]:
    template = load_json(ROOT / "data" / template_name)
    template["tester_id"] = tester_id
    template["episode_id"] = episode_id
    template["model_blind_id"] = model_blind_id
    template["part_type"] = part_type
    if "session_id" in template:
        template["session_id"] = session_id
    return template


def require_tester_id() -> str:
    tester_id = session.get("tester_id")
    if not tester_id:
        raise RuntimeError("tester_id missing")
    return tester_id


app = Flask(__name__, template_folder=str(ROOT / "templates"))
app.secret_key = os.environ.get("LTCW_SECRET_KEY", "dev-only-secret-key")


@app.route("/", methods=["GET"])
def home():
    return render_template("home.html", title="长期情感陪伴能力实验台")


@app.route("/login", methods=["POST"])
def login():
    tester_id = request.form.get("tester_id", "").strip()
    if not tester_id:
        flash("请先输入测试者编号。")
        return redirect(url_for("home"))
    session["tester_id"] = tester_id
    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        tester_id = require_tester_id()
    except RuntimeError:
        flash("请先输入测试者编号。")
        return redirect(url_for("home"))
    return render_template(
        "dashboard.html",
        title="Dashboard",
        tester_id=tester_id,
        episodes=load_episodes()["episodes"],
    )


@app.route("/session/start/<episode_id>/<session_id>/<model_blind_id>", methods=["GET", "POST"])
def start_session(episode_id: str, session_id: str, model_blind_id: str):
    try:
        tester_id = require_tester_id()
    except RuntimeError:
        flash("请先输入测试者编号。")
        return redirect(url_for("home"))

    episode = get_episode(episode_id)
    session_brief = get_session_brief(episode, session_id)

    if request.method == "POST":
        history_summary = request.form.get("history_summary", "").strip()
        max_turns = int(request.form.get("max_turns", "12"))
        run_id = uuid.uuid4().hex
        system_prompt = load_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        if history_summary:
            messages.append({
                "role": "system",
                "content": (
                    "以下是为保持跨 session 连续性而提供的标准化历史摘要。"
                    "请自然使用，不要生硬引用，也不要编造不存在的关系细节。\n\n"
                    f"{history_summary}"
                ),
            })

        state = {
            "run_id": run_id,
            "tester_id": tester_id,
            "episode_id": episode_id,
            "session_id": session_id,
            "part_type": episode["part_type"],
            "model_blind_id": model_blind_id,
            "system_prompt": system_prompt,
            "history_summary_rendered": history_summary,
            "messages": messages,
            "conversation": [],
            "started_at": now_iso(),
            "max_turns": max_turns,
        }
        save_json(create_state_path(run_id), state)
        return redirect(url_for("chat", run_id=run_id))

    return render_template(
        "start_session.html",
        title="开始 Session",
        tester_id=tester_id,
        episode=episode,
        session=session_brief,
        model_blind_id=model_blind_id,
    )


@app.route("/chat/<run_id>", methods=["GET", "POST"])
def chat(run_id: str):
    state_path = create_state_path(run_id)
    if not state_path.exists():
        flash("找不到该 session，可能已结束。")
        return redirect(url_for("dashboard"))

    state = load_json(state_path)
    episode = get_episode(state["episode_id"])
    session_brief = get_session_brief(episode, state["session_id"])

    if request.method == "POST":
        action = request.form.get("action")
        if action == "end":
            return redirect(url_for("finish_session", run_id=run_id))

        user_input = request.form.get("user_input", "").strip()
        if not user_input:
            flash("请输入消息后再发送。")
            return redirect(url_for("chat", run_id=run_id))

        turn_index = sum(1 for item in state["conversation"] if item["role"] == "user") + 1
        if turn_index > state["max_turns"]:
            flash("已达到本次 session 的最大轮数，请结束并填写评分。")
            return redirect(url_for("chat", run_id=run_id))

        model_config = get_model_config(state["model_blind_id"])
        client = create_client(model_config)

        state["messages"].append({"role": "user", "content": user_input})
        state["conversation"].append({
            "turn_index": turn_index,
            "role": "user",
            "timestamp": now_iso(),
            "content": user_input,
        })

        try:
            assistant_reply = chat_once(client, model_config, state["messages"])
        except Exception as exc:
            flash(f"模型调用失败：{exc}")
            save_json(state_path, state)
            return redirect(url_for("chat", run_id=run_id))

        state["messages"].append({"role": "assistant", "content": assistant_reply})
        state["conversation"].append({
            "turn_index": turn_index,
            "role": "assistant",
            "timestamp": now_iso(),
            "content": assistant_reply,
        })
        save_json(state_path, state)
        return redirect(url_for("chat", run_id=run_id))

    return render_template(
        "chat.html",
        title="聊天中",
        state=state,
        conversation=state["conversation"],
        episode=episode,
        session_brief=session_brief,
    )


@app.route("/session/finish/<run_id>", methods=["GET"])
def finish_session(run_id: str):
    state_path = create_state_path(run_id)
    if not state_path.exists():
        flash("找不到该 session 状态。")
        return redirect(url_for("dashboard"))

    state = load_json(state_path)
    log_dir = build_log_dir(
        tester_id=state["tester_id"],
        episode_id=state["episode_id"],
        session_id=state["session_id"],
        model_blind_id=state["model_blind_id"],
    )
    ended_at = now_iso()
    model_config = get_model_config(state["model_blind_id"])

    log_payload = {
        "pilot_name": load_app_config().get("pilot_name", "longterm_companion_v1"),
        "tester_id": state["tester_id"],
        "episode_id": state["episode_id"],
        "session_id": state["session_id"],
        "part_type": state["part_type"],
        "model_blind_id": state["model_blind_id"],
        "model_config_snapshot": sanitize_model_config(model_config),
        "system_prompt_path": str(SYSTEM_PROMPT_PATH.relative_to(ROOT)),
        "history_summary_rendered": state.get("history_summary_rendered", ""),
        "conversation": state["conversation"],
        "started_at": state["started_at"],
        "ended_at": ended_at,
        "max_turns": state["max_turns"],
    }

    save_json(log_dir / "session_log.json", log_payload)
    save_text(log_dir / "transcript.md", render_transcript(state["conversation"], {**state, "ended_at": ended_at}))

    session_rating = build_blank_rating(
        "session_rating_form_template.json",
        state["tester_id"],
        state["episode_id"],
        state["session_id"],
        state["model_blind_id"],
        state["part_type"],
    )
    save_json(log_dir / "session_rating.json", session_rating)

    episode_rating = build_blank_rating(
        "episode_rating_form_template.json",
        state["tester_id"],
        state["episode_id"],
        state["session_id"],
        state["model_blind_id"],
        state["part_type"],
    )
    save_json(log_dir / "episode_rating.json", episode_rating)

    state_path.unlink(missing_ok=True)
    return redirect(
        url_for(
            "rate_session",
            tester_id=state["tester_id"],
            episode_id=state["episode_id"],
            session_id=state["session_id"],
            model_blind_id=state["model_blind_id"],
        )
    )


@app.route("/rate/session/<tester_id>/<episode_id>/<session_id>/<model_blind_id>", methods=["GET", "POST"])
def rate_session(tester_id: str, episode_id: str, session_id: str, model_blind_id: str):
    episode = get_episode(episode_id)
    rating_path = build_log_dir(tester_id, episode_id, session_id, model_blind_id) / "session_rating.json"
    rating_data = load_json(rating_path) if rating_path.exists() else build_blank_rating(
        "session_rating_form_template.json", tester_id, episode_id, session_id, model_blind_id, episode["part_type"]
    )

    if request.method == "POST":
        for field, _ in SESSION_RATING_FIELDS:
            rating_data["ratings"][field] = int(request.form[field])
        rating_data["free_text"]["best_moment"] = request.form.get("best_moment", "").strip()
        rating_data["free_text"]["worst_moment"] = request.form.get("worst_moment", "").strip()
        rating_data["free_text"]["one_sentence_impression"] = request.form.get("one_sentence_impression", "").strip()
        save_json(rating_path, rating_data)
        flash("Session 评分已保存。")
        return redirect(url_for("dashboard"))

    return render_template(
        "rate_session.html",
        title="Session 评分",
        tester_id=tester_id,
        episode_id=episode_id,
        session_id=session_id,
        model_blind_id=model_blind_id,
        score_labels=SCORE_LABELS,
        session_rating_fields=SESSION_RATING_FIELDS,
    )


@app.route("/rate/episode/<episode_id>/<model_blind_id>", methods=["GET", "POST"])
def rate_episode(episode_id: str, model_blind_id: str):
    try:
        tester_id = require_tester_id()
    except RuntimeError:
        flash("请先输入测试者编号。")
        return redirect(url_for("home"))

    episode = get_episode(episode_id)
    rating_path = LOGS_DIR / f"tester_{tester_id}" / episode_id / f"episode_rating_{model_blind_id}.json"

    if rating_path.exists():
        rating_data = load_json(rating_path)
    else:
        rating_data = build_blank_rating(
            "episode_rating_form_template.json",
            tester_id,
            episode_id,
            "",
            model_blind_id,
            episode["part_type"],
        )

    if request.method == "POST":
        for field, _ in EPISODE_RATING_FIELDS:
            rating_data["ratings"][field] = int(request.form[field])
        rating_data["free_text"]["summary_impression"] = request.form.get("summary_impression", "").strip()
        rating_data["free_text"]["main_strength"] = request.form.get("main_strength", "").strip()
        rating_data["free_text"]["main_weakness"] = request.form.get("main_weakness", "").strip()
        rating_data["paired_preference"]["preferred_model_blind_id"] = request.form.get("preferred_model_blind_id", "").strip()
        rating_data["paired_preference"]["reason"] = request.form.get("preference_reason", "").strip()
        save_json(rating_path, rating_data)
        flash("Episode 评分已保存。")
        return redirect(url_for("dashboard"))

    return render_template(
        "rate_episode.html",
        title="Episode 评分",
        tester_id=tester_id,
        episode_id=episode_id,
        model_blind_id=model_blind_id,
        score_labels=SCORE_LABELS,
        episode_rating_fields=EPISODE_RATING_FIELDS,
    )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "time": now_iso()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=True)
