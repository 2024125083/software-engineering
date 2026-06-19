"""사회적 약자를 위한 Easy Kiosk - 수업 시연용 프로토타입.

외부 패키지 없이 Python 3의 Tkinter와 JSON 저장소만 사용한다.
"""

from __future__ import annotations

import json
import platform
import subprocess
import threading
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


APP_TITLE = "사회적 약자를 위한 쉬운 키오스크"
KIOSK_ID = "KIOSK-01"
DATA_DIR = Path(__file__).resolve().parent / "data"
LOG_FILE = DATA_DIR / "usage_logs.json"
CALL_FILE = DATA_DIR / "staff_calls.json"

COLORS = {
    "navy": "#15345B",
    "blue": "#2474D2",
    "sky": "#EAF4FF",
    "yellow": "#FFD84D",
    "red": "#D83A3A",
    "green": "#198754",
    "white": "#FFFFFF",
    "text": "#17212B",
    "muted": "#607080",
    "line": "#D8E2EC",
}


@dataclass(frozen=True)
class Menu:
    menu_id: str
    name: str
    category: str
    price: int
    icon: str


MENUS = [
    Menu("M01", "아메리카노", "커피", 3000, "☕"),
    Menu("M02", "카페라떼", "커피", 4000, "🥛"),
    Menu("M03", "따뜻한 차", "차", 3500, "🍵"),
    Menu("M04", "딸기 주스", "음료", 4500, "🍓"),
    Menu("M05", "샌드위치", "음식", 5500, "🥪"),
    Menu("M06", "케이크", "디저트", 5000, "🍰"),
]


class JsonRepository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def append(self, item: dict) -> None:
        items = self.load()
        items.append(item)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


class TTSAdapter:
    """Windows 내장 음성을 사용하고 실패하면 자막만 유지한다."""

    def __init__(self):
        self.enabled = True

    def speak(self, text: str) -> None:
        if not self.enabled or platform.system() != "Windows":
            return

        def worker() -> None:
            safe = text.replace("'", "''")
            command = (
                "Add-Type -AssemblyName System.Speech; "
                "$voice=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$voice.Speak('{safe}')"
            )
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=20,
                )
            except (OSError, subprocess.SubprocessError):
                pass

        threading.Thread(target=worker, daemon=True).start()


class RecommendationEngine:
    def __init__(self, log_repo: JsonRepository):
        self.log_repo = log_repo

    def ranked(self) -> list[Menu]:
        counts = Counter(
            row.get("menu_id")
            for row in self.log_repo.load()
            if row.get("event_type") == "menu_selected"
        )
        defaults = {"M01": 3, "M02": 2, "M05": 1}
        return sorted(MENUS, key=lambda menu: counts[menu.menu_id] + defaults.get(menu.menu_id, 0), reverse=True)


class EasyKioskApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x760")
        self.minsize(900, 650)
        self.configure(bg=COLORS["white"])
        self.easy_mode = True
        self.cart: list[Menu] = []
        self.step = 1
        self.caption = tk.StringVar(value="화면을 눌러 주문을 시작해 주세요.")
        self.log_repo = JsonRepository(LOG_FILE)
        self.call_repo = JsonRepository(CALL_FILE)
        self.tts = TTSAdapter()
        self.recommendation = RecommendationEngine(self.log_repo)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.show_start()

    def clear(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def log(self, event_type: str, menu_id: str | None = None) -> None:
        self.log_repo.append({
            "log_id": str(uuid.uuid4()),
            "kiosk_id": KIOSK_ID,
            "event_type": event_type,
            "menu_id": menu_id,
            "created_at": self.now(),
        })

    def guide(self, message: str, voice: bool = True) -> None:
        self.caption.set(message)
        if voice:
            self.tts.speak(message)

    def header(self, title: str, progress: str = "") -> None:
        top = tk.Frame(self, bg=COLORS["navy"], height=82)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="쉬운 키오스크", font=("Malgun Gothic", 25, "bold"), bg=COLORS["navy"], fg="white").pack(side="left", padx=28)
        tk.Label(top, text=title, font=("Malgun Gothic", 20, "bold"), bg=COLORS["navy"], fg="white").pack(side="left", padx=30)
        if progress:
            tk.Label(top, text=progress, font=("Malgun Gothic", 17, "bold"), bg=COLORS["yellow"], fg=COLORS["text"], padx=18, pady=10).pack(side="right", padx=22)

    def caption_bar(self) -> None:
        bar = tk.Frame(self, bg=COLORS["sky"], highlightthickness=1, highlightbackground=COLORS["blue"])
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, text="🔊", font=("Segoe UI Emoji", 24), bg=COLORS["sky"]).pack(side="left", padx=(24, 8), pady=15)
        tk.Label(bar, textvariable=self.caption, font=("Malgun Gothic", 18, "bold"), bg=COLORS["sky"], fg=COLORS["text"], anchor="w").pack(side="left", fill="x", expand=True)
        tk.Checkbutton(
            bar, text="음성 안내", variable=tk.BooleanVar(value=self.tts.enabled),
            command=self.toggle_voice, font=("Malgun Gothic", 14), bg=COLORS["sky"],
            activebackground=COLORS["sky"],
        ).pack(side="right", padx=24)

    def toggle_voice(self) -> None:
        self.tts.enabled = not self.tts.enabled
        self.guide("음성 안내를 켰습니다." if self.tts.enabled else "음성 안내를 껐습니다.", voice=self.tts.enabled)

    def big_button(self, parent, text: str, command, color: str = "blue", width: int = 18, height: int = 3, font_size: int = 20) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, width=width, height=height,
            font=("Malgun Gothic", font_size, "bold"), bg=COLORS[color],
            fg="white" if color not in ("yellow", "sky") else COLORS["text"],
            activebackground=COLORS["navy"], activeforeground="white",
            relief="flat", cursor="hand2", bd=0,
        )

    def show_start(self) -> None:
        self.clear()
        self.cart.clear()
        self.header("처음 화면")
        body = tk.Frame(self, bg=COLORS["white"])
        body.pack(expand=True, fill="both", padx=70, pady=35)
        tk.Label(body, text="원하는 이용 방법을 선택해 주세요", font=("Malgun Gothic", 30, "bold"), bg="white", fg=COLORS["text"]).pack(pady=(15, 35))
        buttons = tk.Frame(body, bg="white")
        buttons.pack(expand=True)
        self.big_button(buttons, "👆  이지모드\n큰 글씨 · 음성 안내", lambda: self.enter_mode(True), "blue", 20, 4, 24).grid(row=0, column=0, padx=25)
        self.big_button(buttons, "일반모드\n기본 화면", lambda: self.enter_mode(False), "navy", 20, 4, 22).grid(row=0, column=1, padx=25)
        tk.Button(body, text="⚙ 관리자", command=self.show_admin, font=("Malgun Gothic", 13), bg="white", fg=COLORS["muted"], relief="flat", cursor="hand2").pack(anchor="e")
        self.caption_bar()
        self.guide("이지모드는 큰 글씨와 음성으로 쉽게 안내합니다.")

    def enter_mode(self, easy: bool) -> None:
        self.easy_mode = easy
        self.log("easy_mode_started" if easy else "normal_mode_started")
        self.show_menu()

    def show_menu(self) -> None:
        self.clear()
        self.step = 1
        self.header("메뉴 선택", "1 / 3 단계")
        body = tk.Frame(self, bg="white")
        body.pack(fill="both", expand=True, padx=32, pady=18)
        tk.Label(body, text="추천 메뉴부터 보여드려요" if self.easy_mode else "메뉴를 선택하세요", font=("Malgun Gothic", 25 if self.easy_mode else 20, "bold"), bg="white", fg=COLORS["text"]).pack(anchor="w", pady=(0, 12))
        grid = tk.Frame(body, bg="white")
        grid.pack(fill="both", expand=True)
        menus = self.recommendation.ranked()
        visible = menus[:6] if self.easy_mode else MENUS
        for index, menu in enumerate(visible):
            text = f"{menu.icon}  {menu.name}\n{menu.price:,}원"
            button = tk.Button(
                grid, text=text, command=lambda item=menu: self.select_menu(item),
                font=("Malgun Gothic", 19 if self.easy_mode else 16, "bold"),
                bg=COLORS["sky"] if index < 3 else "white", fg=COLORS["text"],
                activebackground=COLORS["yellow"], relief="solid", bd=1,
                highlightbackground=COLORS["line"], cursor="hand2",
            )
            button.grid(row=index // 3, column=index % 3, padx=10, pady=10, sticky="nsew")
        for col in range(3):
            grid.columnconfigure(col, weight=1)
        for row in range(2):
            grid.rowconfigure(row, weight=1)
        actions = tk.Frame(body, bg="white")
        actions.pack(fill="x", pady=(10, 0))
        self.big_button(actions, "🏠 처음으로", self.show_start, "navy", 11, 2, 16).pack(side="left")
        self.big_button(actions, "🙋 직원 호출", self.show_staff_call, "red", 11, 2, 16).pack(side="right")
        self.caption_bar()
        self.guide("원하는 메뉴를 한 번 눌러 주세요.")

    def select_menu(self, menu: Menu) -> None:
        self.cart = [menu]
        self.log("menu_selected", menu.menu_id)
        self.show_options()

    def show_options(self) -> None:
        self.clear()
        self.step = 2
        menu = self.cart[0]
        self.header("선택 확인", "2 / 3 단계")
        body = tk.Frame(self, bg="white")
        body.pack(expand=True, fill="both", padx=70, pady=35)
        tk.Label(body, text=f"{menu.icon}", font=("Segoe UI Emoji", 65), bg="white").pack()
        tk.Label(body, text=menu.name, font=("Malgun Gothic", 32, "bold"), bg="white", fg=COLORS["text"]).pack(pady=8)
        tk.Label(body, text=f"{menu.price:,}원", font=("Malgun Gothic", 24), bg="white", fg=COLORS["blue"]).pack()
        tk.Label(body, text="이 메뉴가 맞나요?", font=("Malgun Gothic", 27, "bold"), bg="white", fg=COLORS["text"]).pack(pady=30)
        row = tk.Frame(body, bg="white")
        row.pack()
        self.big_button(row, "← 다시 고르기", self.show_menu, "navy", 13, 3, 18).pack(side="left", padx=18)
        self.big_button(row, "맞아요  →", self.show_summary, "green", 13, 3, 18).pack(side="left", padx=18)
        self.caption_bar()
        self.guide(f"{menu.name}, {menu.price:,}원입니다. 이 메뉴가 맞으면 맞아요 버튼을 눌러 주세요.")

    def show_summary(self) -> None:
        self.clear()
        self.step = 3
        menu = self.cart[0]
        self.header("주문 확인", "3 / 3 단계")
        body = tk.Frame(self, bg="white")
        body.pack(expand=True, fill="both", padx=75, pady=35)
        tk.Label(body, text="마지막으로 확인해 주세요", font=("Malgun Gothic", 29, "bold"), bg="white", fg=COLORS["text"]).pack(pady=(10, 30))
        card = tk.Frame(body, bg=COLORS["sky"], padx=30, pady=24, highlightthickness=1, highlightbackground=COLORS["blue"])
        card.pack(fill="x")
        tk.Label(card, text=f"{menu.icon}  {menu.name}", font=("Malgun Gothic", 25, "bold"), bg=COLORS["sky"], fg=COLORS["text"]).pack(side="left")
        tk.Label(card, text=f"{menu.price:,}원", font=("Malgun Gothic", 25, "bold"), bg=COLORS["sky"], fg=COLORS["blue"]).pack(side="right")
        row = tk.Frame(body, bg="white")
        row.pack(pady=40)
        self.big_button(row, "← 수정하기", self.show_menu, "navy", 13, 3, 18).pack(side="left", padx=18)
        self.big_button(row, "주문하기", self.complete_order, "green", 13, 3, 18).pack(side="left", padx=18)
        self.caption_bar()
        self.guide("주문 내용이 맞으면 주문하기 버튼을 눌러 주세요.")

    def complete_order(self) -> None:
        self.log("order_completed", self.cart[0].menu_id)
        self.clear()
        self.header("주문 완료")
        body = tk.Frame(self, bg="white")
        body.pack(expand=True)
        tk.Label(body, text="✓", font=("Arial", 85, "bold"), bg="white", fg=COLORS["green"]).pack()
        tk.Label(body, text="주문이 완료되었습니다", font=("Malgun Gothic", 34, "bold"), bg="white", fg=COLORS["text"]).pack(pady=16)
        tk.Label(body, text="결제는 시연용으로 처리되었습니다.", font=("Malgun Gothic", 18), bg="white", fg=COLORS["muted"]).pack(pady=8)
        self.big_button(body, "처음 화면으로", self.show_start, "blue", 14, 3, 18).pack(pady=30)
        self.caption_bar()
        self.guide("주문이 완료되었습니다. 이용해 주셔서 감사합니다.")

    def show_staff_call(self) -> None:
        self.clear()
        self.header("직원 호출")
        body = tk.Frame(self, bg="white")
        body.pack(expand=True)
        tk.Label(body, text="🙋", font=("Segoe UI Emoji", 70), bg="white").pack()
        tk.Label(body, text="직원을 불러드릴까요?", font=("Malgun Gothic", 32, "bold"), bg="white", fg=COLORS["text"]).pack(pady=20)
        row = tk.Frame(body, bg="white")
        row.pack(pady=25)
        self.big_button(row, "취소", self.show_menu, "navy", 12, 3, 18).pack(side="left", padx=18)
        self.big_button(row, "직원 호출", self.request_staff, "red", 12, 3, 18).pack(side="left", padx=18)
        self.caption_bar()
        self.guide("도움이 필요하면 직원 호출 버튼을 눌러 주세요.")

    def request_staff(self) -> None:
        existing = [row for row in self.call_repo.load() if row.get("status") == "requested"]
        if existing:
            messagebox.showinfo("직원 호출", "이미 직원을 호출했습니다. 잠시만 기다려 주세요.")
        else:
            call = {
                "call_id": str(uuid.uuid4()), "kiosk_id": KIOSK_ID,
                "call_time": self.now(), "status": "requested", "resolved_time": None,
            }
            self.call_repo.append(call)
            self.log("staff_called")
        self.clear()
        self.header("직원 호출 접수")
        body = tk.Frame(self, bg="white")
        body.pack(expand=True)
        tk.Label(body, text="직원 호출이 접수되었습니다", font=("Malgun Gothic", 32, "bold"), bg="white", fg=COLORS["green"]).pack(pady=25)
        tk.Label(body, text="잠시만 기다려 주세요.", font=("Malgun Gothic", 23), bg="white", fg=COLORS["text"]).pack()
        self.big_button(body, "메뉴로 돌아가기", self.show_menu, "blue", 15, 3, 17).pack(pady=35)
        self.caption_bar()
        self.guide("직원 호출이 접수되었습니다. 잠시만 기다려 주세요.")

    def show_admin(self) -> None:
        self.clear()
        self.header("관리자 화면")
        body = tk.Frame(self, bg="white")
        body.pack(fill="both", expand=True, padx=50, pady=25)
        logs = self.log_repo.load()
        calls = self.call_repo.load()
        completed = sum(row.get("event_type") == "order_completed" for row in logs)
        waiting = sum(row.get("status") == "requested" for row in calls)
        tk.Label(body, text="운영 현황 (시연용)", font=("Malgun Gothic", 27, "bold"), bg="white", fg=COLORS["text"]).pack(anchor="w", pady=12)
        stats = tk.Frame(body, bg="white")
        stats.pack(fill="x", pady=15)
        for index, (label, value, color) in enumerate([
            ("전체 이용 이벤트", len(logs), "blue"), ("완료 주문", completed, "green"), ("대기 호출", waiting, "red")
        ]):
            card = tk.Frame(stats, bg=COLORS[color], padx=25, pady=22)
            card.grid(row=0, column=index, padx=8, sticky="nsew")
            stats.columnconfigure(index, weight=1)
            tk.Label(card, text=label, font=("Malgun Gothic", 16, "bold"), bg=COLORS[color], fg="white").pack()
            tk.Label(card, text=str(value), font=("Arial", 34, "bold"), bg=COLORS[color], fg="white").pack()
        tk.Label(body, text="추천 순위", font=("Malgun Gothic", 22, "bold"), bg="white", fg=COLORS["text"]).pack(anchor="w", pady=(25, 8))
        ranking = "   ".join(f"{i + 1}위 {menu.name}" for i, menu in enumerate(self.recommendation.ranked()[:3]))
        tk.Label(body, text=ranking, font=("Malgun Gothic", 18), bg=COLORS["sky"], fg=COLORS["text"], padx=20, pady=18).pack(fill="x")
        self.big_button(body, "처음 화면으로", self.show_start, "navy", 14, 2, 16).pack(side="bottom", pady=18)


if __name__ == "__main__":
    app = EasyKioskApp()
    app.mainloop()
