"""
Health Data Dashboard Module for Lady卡卡.
Renders interactive Plotly Dash charts embedded inside Flask:
- User Profile & BMR / TDEE Cards
- Calorie Breakdown Donut Chart
- Daily Calorie Intake & Burn Trend Chart
- Net Calorie Deficit / Surplus Trend Chart
"""

import datetime
import logging
from typing import Any, Dict

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from access_db import Dailydata, Userdata
from dash import Input, Output, State, dcc, html
from flask import session

logger = logging.getLogger(__name__)


class HealthDashboard:
    def __init__(self, flask_app):
        self.dash_app = dash.Dash(
            server=flask_app,
            routes_pathname_prefix="/dashboard/",
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                "https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;600;700&display=swap",
            ],
            title="Lady卡卡 健康儀表板",
        )
        self.dash_app.layout = self.serve_layout()
        self.init_callbacks()

    def serve_layout(self):
        return html.Div(
            [
                dcc.Location(id="url", refresh=False),
                html.Div(id="page-content"),
            ],
            style={"fontFamily": "'Noto Sans TC', sans-serif", "backgroundColor": "#F8FAFC", "minHeight": "100vh"},
        )

    def init_callbacks(self):
        @self.dash_app.callback(
            Output("page-content", "children"),
            Input("url", "pathname"),
            State("url", "search"),
        )
        def display_page(pathname, search):
            # Extract user_id from path /dashboard/<user_id>
            user_id = "未知"
            if pathname:
                parts = pathname.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "dashboard":
                    user_id = parts[1]
            if user_id == "未知":
                user_id = session.get("user_id", "未知")
            return self.create_layout(user_id)

        @self.dash_app.callback(
            Output("calorie-trend-chart", "figure"),
            Output("net-calories-trend-chart", "figure"),
            Input("play-button", "n_clicks"),
            Input("animation-interval", "n_intervals"),
            State("url", "pathname"),
        )
        def update_charts(n_clicks, n_intervals, pathname):
            user_id = pathname.strip("/").split("/")[-1] if pathname else "未知"
            if n_clicks is None or n_intervals is None:
                days = 15
            else:
                days = min(60, 15 + n_intervals)
            calorie_fig = self.create_calorie_trend_chart(user_id, days)
            net_calories_fig = self.create_net_calories_trend_chart(user_id, days)
            return calorie_fig, net_calories_fig

        @self.dash_app.callback(
            Output("animation-interval", "disabled"),
            Input("play-button", "n_clicks"),
            State("animation-interval", "disabled"),
        )
        def toggle_animation(n_clicks, current_state):
            if n_clicks is None:
                return True
            return not current_state

    def create_layout(self, user_id: str):
        user_info = self.get_user_info(user_id)
        today_data = self.get_today_data(user_id)
        user_name = user_info.get("name", "健康夥伴")

        layout = html.Div(
            [
                html.Div(
                    [
                        html.H1(
                            "✨ Lady卡卡 專屬健康數據儀表板 ✨",
                            className="text-center font-weight-bold mb-2",
                            style={"color": "#334155", "fontSize": "26px", "fontWeight": "700"},
                        ),
                        html.P(
                            f"嗨，{user_name}！來看看您近期的飲食與運動熱量趨勢吧！",
                            className="text-center text-muted mb-4",
                        ),
                    ],
                    className="pt-4",
                ),
                self.create_user_info_section(user_info, today_data),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        dcc.Graph(
                                            figure=self.create_calorie_pie_chart(today_data, user_info),
                                            config={"displayModeBar": False},
                                        )
                                    ]
                                ),
                                className="shadow-sm border-0 mb-4",
                            ),
                            md=12,
                        )
                    ]
                ),
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div(
                                [
                                    dbc.Button(
                                        "▶ 播放 / 暫停 動態趨勢",
                                        id="play-button",
                                        color="primary",
                                        className="mb-3",
                                        style={
                                            "backgroundColor": "#EC4899",
                                            "borderColor": "#EC4899",
                                            "borderRadius": "20px",
                                            "padding": "6px 20px",
                                        },
                                    ),
                                ]
                            ),
                            dcc.Graph(
                                id="calorie-trend-chart",
                                figure=self.create_calorie_trend_chart(user_id, 15),
                                config={"displayModeBar": False},
                            ),
                            html.Hr(className="my-4"),
                            dcc.Graph(
                                id="net-calories-trend-chart",
                                figure=self.create_net_calories_trend_chart(user_id, 15),
                                config={"displayModeBar": False},
                            ),
                        ]
                    ),
                    className="shadow-sm border-0 mb-4",
                ),
                dcc.Interval(
                    id="animation-interval",
                    interval=500,
                    n_intervals=0,
                    max_intervals=45,
                    disabled=True,
                ),
            ],
            className="container py-3",
            style={"maxWidth": "900px"},
        )
        return layout

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        try:
            user_data = Userdata(user_id)
            user_info = user_data.search_data("u_id", user_id) or {}
            if user_info:
                user_info["bmr"] = self.calculate_bmr(user_info)
                user_info["tdee"] = self.calculate_tdee(user_info["bmr"], user_info.get("activity_level", 1.2))
                user_info["target_weight"] = self.get_latest_target_weight(user_id, user_info.get("weight", 60.0))
                user_info["goal_achievement"] = self.calculate_goal_achievement(
                    user_info.get("weight", 60.0), user_info["target_weight"]
                )
            else:
                user_info = {
                    "name": "訪客",
                    "height": 165,
                    "weight": 60,
                    "bmr": 1400.0,
                    "tdee": 1700.0,
                    "target_weight": 55,
                    "goal_achievement": 100.0,
                }
            return user_info
        except Exception as e:
            logger.error(f"Error in get_user_info: {e}")
            return {}

    def create_user_info_section(self, user_info: Dict[str, Any], today_data: pd.DataFrame):
        total_calories = float(today_data["food_calories"].sum()) if not today_data.empty and "food_calories" in today_data else 0.0
        total_exercise = float(today_data["exercise_duration"].sum()) if not today_data.empty and "exercise_duration" in today_data else 0.0

        bmr_val = user_info.get("bmr", 1400.0)
        tdee_val = user_info.get("tdee", 1700.0)
        weight_val = user_info.get("weight", "--")
        target_val = user_info.get("target_weight", "--")
        achievement = user_info.get("goal_achievement", 100.0)

        card = dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H5("📊 基礎能量代謝", className="font-weight-bold mb-3", style={"color": "#475569"}),
                                    html.P(f"身高：{user_info.get('height', '--')} cm", className="mb-1"),
                                    html.P(f"基礎代謝率 (BMR)：{bmr_val:.0f} 大卡", className="mb-1"),
                                    html.P(f"每日總能量消耗 (TDEE)：{tdee_val:.0f} 大卡", className="mb-1"),
                                    html.P(f"今日已攝取熱量：{total_calories:.0f} 大卡", className="mb-1 text-danger font-weight-bold"),
                                    html.P(f"今日已運動時間：{total_exercise:.0f} 分鐘", className="mb-0 text-success"),
                                ],
                                md=6,
                                className="border-end",
                            ),
                            dbc.Col(
                                [
                                    html.H5("🎯 體態目標達成", className="font-weight-bold mb-3", style={"color": "#475569"}),
                                    html.P(f"目前體重：{weight_val} kg", className="mb-1"),
                                    html.P(f"目標體重：{target_val} kg", className="mb-2"),
                                    html.Small("目標達成進度", className="text-muted"),
                                    self.create_progress_bar(achievement),
                                ],
                                md=6,
                                className="d-flex flex-column justify-content-center",
                            ),
                        ]
                    )
                ]
            ),
            className="shadow-sm border-0 mb-4",
        )
        return card

    def create_progress_bar(self, achievement: float):
        display_val = min(100.0, max(0.0, achievement))
        return dbc.Progress(
            value=display_val,
            label=f"{achievement:.1f}%",
            style={"height": "24px", "borderRadius": "12px"},
            className="mt-1",
            color="success" if achievement >= 80 else "warning" if achievement >= 50 else "info",
            striped=True,
            animated=True,
        )

    def create_calorie_pie_chart(self, data: pd.DataFrame, user_info: Dict[str, Any]):
        total_food_calories = float(data["food_calories"].sum()) if not data.empty and "food_calories" in data else 0.0
        total_burned_calories = float(data["calories_burned"].sum()) if not data.empty and "calories_burned" in data else 0.0
        bmr_calories = float(user_info.get("bmr", 1400.0))

        values = [max(1, total_food_calories), bmr_calories, max(1, total_burned_calories)]
        labels = ["今日食物攝取", "基礎代謝消耗", "運動主動燃燒"]
        colors = ["#FCA5A5", "#86EFAC", "#93C5FD"]

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.45,
                    pull=[0.05, 0, 0],
                    marker=dict(colors=colors),
                    textinfo="label+percent",
                    textfont_size=13,
                )
            ]
        )
        fig.update_layout(
            title=dict(text="🔥 今日熱量收支圓餅圖", font=dict(size=16, color="#334155"), x=0.5),
            showlegend=True,
            height=340,
            margin=dict(t=50, b=20, l=20, r=20),
        )
        return fig

    def create_calorie_trend_chart(self, user_id: str, days: int = 15):
        df = self.get_sixty_day_data(user_id)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(title="尚無足夠的歷史數據，開始記錄後將為您繪製趨勢圖！")
            return fig

        daily_totals = (
            df.groupby("date")
            .agg(
                total_food_calories=("food_calories", "sum"),
                total_exercise_calories=("calories_burned", "sum"),
                TDEE=("TDEE", "first"),
                bmr_target=("bmr_target", "max"),
            )
            .reset_index()
        )
        daily_totals["date"] = pd.to_datetime(daily_totals["date"])
        daily_totals = daily_totals.sort_values("date").tail(days)

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=daily_totals["date"],
                y=daily_totals["total_food_calories"],
                name="食物攝取熱量",
                marker_color="rgba(248, 113, 113, 0.8)",
            )
        )
        fig.add_trace(
            go.Bar(
                x=daily_totals["date"],
                y=daily_totals["total_exercise_calories"],
                name="運動燃燒熱量",
                marker_color="rgba(96, 165, 250, 0.8)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=daily_totals["date"],
                y=daily_totals["TDEE"],
                name="每日TDEE基準",
                line=dict(color="#10B981", width=2, dash="dash"),
            )
        )
        fig.update_layout(
            title=dict(text=f"📈 卡路里收支歷史趨勢 (近 {days} 天)", font=dict(size=15)),
            barmode="group",
            height=380,
            margin=dict(t=50, b=40, l=40, r=20),
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        )
        return fig

    def create_net_calories_trend_chart(self, user_id: str, days: int = 15):
        df = self.get_sixty_day_data(user_id)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(title="尚無足夠的歷史數據")
            return fig

        daily_totals = (
            df.groupby("date")
            .agg(
                total_food_calories=("food_calories", "sum"),
                total_exercise_calories=("calories_burned", "sum"),
                TDEE=("TDEE", "first"),
                bmr_target=("bmr_target", "max"),
            )
            .reset_index()
        )
        daily_totals["date"] = pd.to_datetime(daily_totals["date"])
        daily_totals = daily_totals.sort_values("date").tail(days)
        daily_totals["net_calories"] = (
            daily_totals["total_food_calories"] - daily_totals["TDEE"] - daily_totals["total_exercise_calories"]
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=daily_totals["date"],
                y=daily_totals["net_calories"],
                name="每日熱量赤字/盈餘",
                line=dict(color="#F97316", width=2.5),
                mode="lines+markers",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=daily_totals["date"],
                y=[0] * len(daily_totals),
                name="熱量平衡零線",
                line=dict(color="#64748B", width=1, dash="dot"),
            )
        )
        fig.update_layout(
            title=dict(text=f"⚖️ 每日淨熱量赤字走勢 (低於0代表消耗大於攝取，正在燃脂！)", font=dict(size=14)),
            height=340,
            margin=dict(t=50, b=40, l=40, r=20),
            legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        )
        return fig

    def get_today_data(self, user_id: str) -> pd.DataFrame:
        daily_data = Dailydata(user_id)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        all_data = daily_data.search_all_data("date", "1d")
        if not all_data:
            return pd.DataFrame()
        df = pd.DataFrame(all_data)
        if df.empty:
            return df
        return df[(df["date"] == today) & (df["u_id"] == user_id)]

    def get_sixty_day_data(self, user_id: str) -> pd.DataFrame:
        daily_data = Dailydata(user_id)
        all_data = daily_data.search_all_data("date", "60d")
        if not all_data:
            return pd.DataFrame()
        df = pd.DataFrame(all_data)
        if df.empty:
            return df
        user_info = self.get_user_info(user_id)
        tdee_val = user_info.get("tdee", 1700.0)
        df["TDEE"] = tdee_val
        if "bmr_target" not in df.columns:
            df["bmr_target"] = 0.0
        return df[df["u_id"] == user_id]

    @staticmethod
    def calculate_bmr(user_info: Dict[str, Any]) -> float:
        weight = float(user_info.get("weight", 60.0))
        height = float(user_info.get("height", 165.0))
        age = int(user_info.get("age", 25))
        is_male = user_info.get("gender") in (1, True, "1", "male")
        if is_male:
            return 10.0 * weight + 6.25 * height - 5.0 * age + 5.0
        return 10.0 * weight + 6.25 * height - 5.0 * age - 161.0

    @staticmethod
    def calculate_tdee(bmr: float, activity_level: float) -> float:
        return bmr * float(activity_level or 1.2)

    @staticmethod
    def calculate_goal_achievement(actual_weight: float, target_weight: float) -> float:
        if actual_weight <= 0 or target_weight <= 0:
            return 100.0
        if actual_weight <= target_weight:
            return 100.0
        # Percentage progress towards goal
        diff = actual_weight - target_weight
        return max(0.0, min(100.0, 100.0 - (diff / target_weight) * 100.0))

    @staticmethod
    def get_latest_target_weight(user_id: str, actual_weight: float) -> float:
        daily_data = Dailydata(user_id)
        all_data = daily_data.search_all_data("date", "60d")
        if all_data:
            df = pd.DataFrame(all_data)
            if not df.empty and "weight_target" in df.columns:
                valid = df[(df["u_id"] == user_id) & (df["weight_target"] > 0)]
                if not valid.empty:
                    latest = valid.sort_values(by="date", ascending=False).iloc[0]
                    return float(latest["weight_target"])
        return float(actual_weight)

    def render_dashboard(self, user_id: str):
        session["user_id"] = user_id
        return self.dash_app.index()