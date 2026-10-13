"""Manim atoms for Template v9 Kit (build-time only).

Grammar mirrors apps.sportskit.plates: duel zones + lime winners, leader
rows, poster split + brush + ticker, goal punch, fixture/score/quote/welcome.
DEMO data only; production values come from reviewed graphic_data.
"""

from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    FadeIn,
    FadeOut,
    Rectangle,
    Scene,
    Text,
    VGroup,
    Write,
    config,
    rate_functions,
)

VI_FONT = "Arial"
DISPLAY_FONT = "Arial"
INK = "#0B0D10"
PAPER = "#F5F1E6"
KIT_RED = "#C8102E"
NAVY = "#0A1A3C"
ORANGE = "#E8590C"
LIME = "#8CFF00"
MUTED = "#9AA3A8"

config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 8
config.frame_height = 8 * 16 / 9


def _title(text: str, size: int = 44, color: str = PAPER) -> Text:
    return Text(str(text)[:60], font=DISPLAY_FONT, font_size=size, color=color)


def _body(text: str, size: int = 22, color: str = PAPER) -> Text:
    return Text(str(text)[:80], font=VI_FONT, font_size=size, color=color)


class DuelColumns(Scene):
    def construct(self) -> None:
        bg_left = Rectangle(width=4, height=config.frame_height, fill_color=NAVY,
                            fill_opacity=1, stroke_width=0).move_to(LEFT * 2)
        bg_right = Rectangle(width=4, height=config.frame_height, fill_color=ORANGE,
                             fill_opacity=1, stroke_width=0).move_to(RIGHT * 2)
        self.add(bg_left, bg_right)
        header = _title("SO SANH DOI DAU", 40)
        header.to_edge(UP, buff=0.8)
        self.play(FadeIn(header, shift=DOWN * 0.3), run_time=0.4,
                  rate_func=rate_functions.ease_out_cubic)
        rows = [(("BAN THANG"), ("45", LIME), ("38", PAPER)),
                (("KIEN TAO"), ("30", PAPER), ("30", PAPER))]
        y = 1.6
        for label, (lv, lc), (rv, rc) in rows:
            lab = _body(label, 22)
            lab.move_to(UP * y)
            left = _title(lv, 72, lc).move_to(LEFT * 2 + UP * (y - 0.9))
            right = _title(rv, 72, rc).move_to(RIGHT * 2 + UP * (y - 0.9))
            self.play(FadeIn(lab), FadeIn(left, scale=0.6), FadeIn(right, scale=0.6),
                      run_time=0.45, rate_func=rate_functions.ease_out_back)
            y -= 2.6
        self.wait(0.6)


class StatLeader(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=KIT_RED, fill_opacity=1, stroke_width=0)
        self.add(bg)
        for label, value in (("BAN THANG", "19"), ("KIEN TAO", "7"), ("TRAN DAU", "63")):
            lab = _body(label, 22)
            num = _title(value, 84, "#000000")
            group = VGroup(lab, num).arrange(DOWN, buff=0.12).move_to(LEFT * 1.6 + UP * 2)
            # stack groups by shifting down
            group.shift(DOWN * (["BAN THANG", "KIEN TAO", "TRAN DAU"].index(label) * 2.4 - 2.4))
            self.play(FadeIn(group, shift=RIGHT * 0.4), run_time=0.35,
                      rate_func=rate_functions.ease_out_cubic)
        foot = _title("STATS", 56)
        foot.to_edge(DOWN, buff=1.0)
        self.play(FadeIn(foot, shift=UP * 0.3), run_time=0.35)
        self.wait(0.6)


class PosterSide(Scene):
    def construct(self) -> None:
        photo = Rectangle(width=config.frame_width * 0.46, height=config.frame_height,
                          fill_color="#1a1d20", fill_opacity=1,
                          stroke_width=0).to_edge(LEFT, buff=0)
        field = Rectangle(width=config.frame_width * 0.54, height=config.frame_height,
                          fill_color=KIT_RED, fill_opacity=1,
                          stroke_width=0).to_edge(RIGHT, buff=0)
        self.add(photo, field)
        tape = _body("NGUYEN VAN A  •  NGUYEN VAN A", 16)
        tape.to_edge(UP, buff=0.35).rotate(-0.14)
        name = Text("VAN A", font=DISPLAY_FONT, font_size=72, color="#000000", slant="ITALIC")
        name.next_to(tape, DOWN, buff=0.5)
        tag = _body("#19 TIEN DAO", 22)
        tag.next_to(name, DOWN, buff=0.3)
        self.play(FadeIn(tape, shift=DOWN * 0.2), run_time=0.3)
        self.play(FadeIn(name, scale=0.85), run_time=0.45,
                  rate_func=rate_functions.ease_out_back)
        self.play(FadeIn(tag, shift=UP * 0.2), run_time=0.3)
        for v, l in (("19", "BAN"), ("7", "KIEN TAO")):
            row = VGroup(_title(v, 56), _body(l, 18)).arrange(DOWN, buff=0.08)
            row.move_to(RIGHT * 2.2 + DOWN * (0.5 if v == "19" else 2.2))
            self.play(FadeIn(row, shift=UP * 0.25), run_time=0.3)
        self.wait(0.6)


class GoalPunch(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=KIT_RED, fill_opacity=1, stroke_width=0)
        self.add(bg)
        giant = Text("GOAL", font=DISPLAY_FONT, font_size=170, color="#7E0A1E")
        self.play(FadeIn(giant, scale=1.2), run_time=0.4,
                  rate_func=rate_functions.ease_out_cubic)
        chant = _title("SIEU PHAM MO TY SO", 44)
        self.play(FadeIn(chant, scale=0.7), run_time=0.35,
                  rate_func=rate_functions.ease_out_back)
        pill = Rectangle(width=3.0, height=0.9, fill_color=PAPER, fill_opacity=1,
                         stroke_width=0).next_to(chant, DOWN, buff=0.5)
        score = Text("1 - 0", font=DISPLAY_FONT, font_size=40, color=INK)
        score.move_to(pill.get_center())
        self.play(FadeIn(pill, shift=UP * 0.3), FadeIn(score, shift=UP * 0.3),
                  run_time=0.35)
        self.wait(0.6)


class FixtureCard(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=KIT_RED, fill_opacity=1, stroke_width=0)
        self.add(bg)
        header = _title("NEXT MATCH", 52)
        header.to_edge(UP, buff=1.0)
        versus = _title("HA NOI  V  NAM DINH", 32)
        versus.next_to(header, DOWN, buff=0.4)
        when = _body("19:15 CHU NHAT  •  SAN HANG DAY", 20)
        when.next_to(versus, DOWN, buff=0.35)
        self.play(FadeIn(header, scale=0.9), run_time=0.35,
                  rate_func=rate_functions.ease_out_back)
        self.play(FadeIn(versus, shift=UP * 0.25), FadeIn(when, shift=UP * 0.25),
                  run_time=0.4)
        self.wait(0.6)


class ScoreBug(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=INK, fill_opacity=1, stroke_width=0)
        self.add(bg)
        bug = VGroup(_title("2", 110), _title("-", 80), _title("0", 110))
        bug.arrange(RIGHT, buff=0.3).move_to(UP * 1.2)
        state = _title("FULL TIME", 60)
        state.next_to(bug, DOWN, buff=0.5)
        self.play(FadeIn(bug, scale=0.8), run_time=0.45,
                  rate_func=rate_functions.ease_out_back)
        self.play(Write(state, run_time=0.5))
        self.wait(0.6)


class QuoteReveal(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=KIT_RED, fill_opacity=1, stroke_width=0)
        self.add(bg)
        box = Rectangle(width=6.4, height=4.2, fill_color=PAPER, fill_opacity=1,
                        stroke_width=0)
        mark = _title("“", 110, KIT_RED).move_to(UP * 1.6 + LEFT * 2.4)
        quote = _body("Chung toi den day de thang.", 26, INK)
        quote.next_to(mark, DOWN, buff=0.2)
        who = _body("HLV TRUONG", 22, INK)
        who.next_to(quote, DOWN, buff=0.4)
        self.play(FadeIn(box, shift=UP * 0.3), run_time=0.4,
                  rate_func=rate_functions.ease_out_cubic)
        self.play(FadeIn(mark, scale=0.6), Write(quote, run_time=0.6),
                  FadeIn(who, run_time=0.3))
        self.wait(0.6)


class WelcomeCard(Scene):
    def construct(self) -> None:
        bg = Rectangle(width=config.frame_width, height=config.frame_height,
                       fill_color=KIT_RED, fill_opacity=1, stroke_width=0)
        self.add(bg)
        header = _title("WELCOME", 64)
        header.to_edge(UP, buff=1.2)
        pill = Rectangle(width=4.6, height=0.9, fill_color=INK, fill_opacity=1,
                         stroke_width=0)
        pill.move_to(DOWN * 2.5)
        who = _body("PHAM VAN D", 26)
        who.move_to(pill.get_center())
        self.play(FadeIn(header, shift=DOWN * 0.3), run_time=0.4,
                  rate_func=rate_functions.ease_out_cubic)
        self.play(FadeIn(pill, shift=UP * 0.3), FadeIn(who, shift=UP * 0.3),
                  run_time=0.35)
        self.wait(0.6)
